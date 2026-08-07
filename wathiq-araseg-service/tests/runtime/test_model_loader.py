from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.artifacts import validate_artifact_from_manifest  # noqa: E402
from wathiq_araseg.artifacts.manifest import (  # noqa: E402
    ArtifactManifest,
    InferenceConfig,
    ManifestFileEntry,
    ValidatedBlindResult,
)
from wathiq_araseg.runtime.model_loader import (  # noqa: E402
    LoadedModelRuntime,
    ModelLoadError,
    RuntimeConfigurationMismatchError,
    RuntimeDependencyError,
    SmokeInferenceError,
    TokenizerLoadError,
    UnsupportedDeviceError,
    _RuntimeDependencies,
    load_local_model_runtime,
    run_smoke_inference,
)


class _FakeTensor:
    def __init__(self, shape: tuple[int, ...]) -> None:
        self.shape = shape
        self.moved_to: list[str] = []

    def to(self, device: str) -> _FakeTensor:
        self.moved_to.append(device)
        return self


class _FakeFiniteResult:
    def __init__(self, value: bool) -> None:
        self._value = value

    def all(self) -> _FakeFiniteResult:
        return self

    def item(self) -> bool:
        return self._value


class _FakeLogits:
    def __init__(self, shape: tuple[int, ...], all_finite: bool = True) -> None:
        self.shape = shape
        self._all_finite = all_finite


class _FakeTokenizer:
    def __init__(self, *, vocab_size: int = 30001, is_fast: bool = True) -> None:
        self.vocab_size = vocab_size
        self.is_fast = is_fast

    def __len__(self) -> int:
        return self.vocab_size

    def __call__(self, _text: str, **_kwargs) -> dict[str, _FakeTensor]:
        return {
            "input_ids": _FakeTensor((1, 6)),
            "attention_mask": _FakeTensor((1, 6)),
        }


class _FakeModel:
    def __init__(self, *, num_labels: int = 2) -> None:
        self.config = types.SimpleNamespace(num_labels=num_labels)
        self.training = True
        self.eval_called = False
        self.to_calls: list[str] = []

    def to(self, device: str) -> _FakeModel:
        self.to_calls.append(device)
        return self

    def eval(self) -> _FakeModel:
        self.training = False
        self.eval_called = True
        return self

    def __call__(self, **_kwargs) -> types.SimpleNamespace:
        return types.SimpleNamespace(logits=_FakeLogits((1, 6, self.config.num_labels)))


class _FakeTokenizerFactory:
    def __init__(self, tokenizer: _FakeTokenizer | None = None, side_effect=None) -> None:
        self.tokenizer = tokenizer or _FakeTokenizer()
        self.side_effect = side_effect
        self.calls: list[dict[str, object]] = []

    def from_pretrained(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        if self.side_effect is not None:
            raise self.side_effect
        return self.tokenizer


class _FakeModelFactory:
    def __init__(self, model: _FakeModel | None = None, side_effect=None) -> None:
        self.model = model or _FakeModel()
        self.side_effect = side_effect
        self.calls: list[dict[str, object]] = []

    def from_pretrained(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        if self.side_effect is not None:
            raise self.side_effect
        return self.model


class _FakeTorchModule:
    def __init__(self) -> None:
        self.inference_mode_entered = False

    @contextmanager
    def inference_mode(self):
        self.inference_mode_entered = True
        yield

    def isfinite(self, logits: _FakeLogits) -> _FakeFiniteResult:
        return _FakeFiniteResult(logits._all_finite)


def _build_manifest() -> ArtifactManifest:
    return ArtifactManifest(
        schema_version="1.0",
        provider="AraSeg",
        track="PA",
        model_version="fixture-model",
        source_run="fixture-run",
        artifact_directory="best_model",
        model_file="model.safetensors",
        model_sha256="7d76a8a15a302800b2ba4dfafb3815f50a03370a5b12c7d6734491ac68bfb9d1",
        architecture="BertForTokenClassification",
        tokenizer_class="BertTokenizer",
        number_of_labels=2,
        vocabulary_size=30001,
        inference=InferenceConfig(
            max_length=512,
            stride=64,
            default_threshold=0.567,
            end_punctuation_threshold=0.32,
            paragraph_rule_enabled=True,
            force_last_enabled=True,
        ),
        validated_blind_result=ValidatedBlindResult(
            precision=0.934,
            recall=0.939,
            f1=0.934,
            submission_id=861529,
        ),
        files={
            "model.safetensors": ManifestFileEntry(
                size_bytes=1,
                sha256="7d76a8a15a302800b2ba4dfafb3815f50a03370a5b12c7d6734491ac68bfb9d1",
            ),
        },
    )


class RuntimeLoaderUnitTests(unittest.TestCase):
    def test_existing_validator_runs_before_model_loading(self) -> None:
        manifest = _build_manifest()
        events: list[str] = []
        tokenizer_factory = _FakeTokenizerFactory()
        model_factory = _FakeModelFactory()
        dependencies = _RuntimeDependencies(
            torch_module=_FakeTorchModule(),
            auto_tokenizer=tokenizer_factory,
            auto_model_for_token_classification=model_factory,
        )

        with mock.patch(
            "wathiq_araseg.runtime.model_loader.load_manifest",
            return_value=manifest,
        ), mock.patch(
            "wathiq_araseg.runtime.model_loader.validate_artifact_from_manifest",
            side_effect=lambda loaded_manifest, loaded_path: events.append("validate"),
        ), mock.patch(
            "wathiq_araseg.runtime.model_loader._resolve_validated_artifact_directory",
            return_value=Path("best_model"),
        ), mock.patch(
            "wathiq_araseg.runtime.model_loader._import_runtime_dependencies",
            return_value=dependencies,
        ):
            original_tokenizer_loader = tokenizer_factory.from_pretrained
            original_model_loader = model_factory.from_pretrained

            def tokenizer_side_effect(*args, **kwargs):
                events.append("tokenizer")
                return original_tokenizer_loader(*args, **kwargs)

            def model_side_effect(*args, **kwargs):
                events.append("model")
                return original_model_loader(*args, **kwargs)

            tokenizer_factory.from_pretrained = tokenizer_side_effect
            model_factory.from_pretrained = model_side_effect

            load_local_model_runtime(Path("manifest.json"), device="cpu")

        self.assertEqual(events, ["validate", "tokenizer", "model"])

    def test_tokenizer_and_model_load_with_local_files_only(self) -> None:
        runtime, tokenizer_factory, model_factory = self._load_runtime_with_fakes()

        self.assertEqual(runtime.device, "cpu")
        self.assertTrue(tokenizer_factory.calls[0]["kwargs"]["local_files_only"])
        self.assertTrue(model_factory.calls[0]["kwargs"]["local_files_only"])

    def test_model_is_switched_to_eval_mode_and_moved_to_device(self) -> None:
        runtime, _tokenizer_factory, model_factory = self._load_runtime_with_fakes()
        fake_model = model_factory.model

        self.assertIs(runtime.model, fake_model)
        self.assertTrue(fake_model.eval_called)
        self.assertFalse(fake_model.training)
        self.assertEqual(fake_model.to_calls, ["cpu"])

    def test_unsupported_device_is_controlled(self) -> None:
        with self.assertRaises(UnsupportedDeviceError):
            load_local_model_runtime(Path("manifest.json"), device="cuda")

    def test_model_label_count_mismatch_is_controlled(self) -> None:
        with self.assertRaises(RuntimeConfigurationMismatchError):
            self._load_runtime_with_fakes(model=_FakeModel(num_labels=3))

    def test_tokenizer_vocabulary_mismatch_is_controlled(self) -> None:
        with self.assertRaises(RuntimeConfigurationMismatchError):
            self._load_runtime_with_fakes(tokenizer=_FakeTokenizer(vocab_size=123))

    def test_tokenizer_loading_failure_is_controlled_and_chained(self) -> None:
        tokenizer_error = OSError("tokenizer failure")
        with self.assertRaises(TokenizerLoadError) as context:
            self._load_runtime_with_fakes(tokenizer_side_effect=tokenizer_error)

        self.assertIs(context.exception.__cause__, tokenizer_error)

    def test_model_loading_failure_is_controlled_and_chained(self) -> None:
        model_error = ValueError("model failure")
        with self.assertRaises(ModelLoadError) as context:
            self._load_runtime_with_fakes(model_side_effect=model_error)

        self.assertIs(context.exception.__cause__, model_error)

    def test_missing_runtime_dependencies_are_controlled_and_chained(self) -> None:
        dependency_error = RuntimeDependencyError("missing deps")
        manifest = _build_manifest()
        with mock.patch(
            "wathiq_araseg.runtime.model_loader.load_manifest",
            return_value=manifest,
        ), mock.patch(
            "wathiq_araseg.runtime.model_loader.validate_artifact_from_manifest",
            return_value=None,
        ), mock.patch(
            "wathiq_araseg.runtime.model_loader._resolve_validated_artifact_directory",
            return_value=Path("best_model"),
        ), mock.patch(
            "wathiq_araseg.runtime.model_loader._import_runtime_dependencies",
            side_effect=dependency_error,
        ):
            with self.assertRaises(RuntimeDependencyError) as context:
                load_local_model_runtime(Path("manifest.json"), device="cpu")

        self.assertIs(context.exception, dependency_error)

    def test_smoke_inference_uses_torch_inference_mode(self) -> None:
        fake_torch = _FakeTorchModule()
        runtime = LoadedModelRuntime(
            tokenizer=_FakeTokenizer(),
            model=_FakeModel(),
            device="cpu",
            manifest=_build_manifest(),
            artifact_directory=Path("best_model"),
        )

        with mock.patch(
            "wathiq_araseg.runtime.model_loader._import_torch_module",
            return_value=fake_torch,
        ):
            result = run_smoke_inference(runtime, "هذا نص عربي تجريبي")

        self.assertTrue(fake_torch.inference_mode_entered)
        self.assertEqual(result.logits_shape, (1, 6, 2))

    def test_smoke_inference_returns_expected_metadata(self) -> None:
        fake_torch = _FakeTorchModule()
        runtime = LoadedModelRuntime(
            tokenizer=_FakeTokenizer(),
            model=_FakeModel(),
            device="cpu",
            manifest=_build_manifest(),
            artifact_directory=Path("best_model"),
        )

        with mock.patch(
            "wathiq_araseg.runtime.model_loader._import_torch_module",
            return_value=fake_torch,
        ):
            result = run_smoke_inference(runtime, "هذا نص عربي تجريبي")

        self.assertEqual(result.input_token_count, 6)
        self.assertEqual(result.logits_shape, (1, 6, 2))
        self.assertEqual(result.number_of_labels, 2)
        self.assertTrue(result.all_finite)

    def test_smoke_inference_wraps_runtime_failures(self) -> None:
        fake_torch = _FakeTorchModule()
        runtime = LoadedModelRuntime(
            tokenizer=_FakeTokenizer(),
            model=_FailingSmokeModel(),
            device="cpu",
            manifest=_build_manifest(),
            artifact_directory=Path("best_model"),
        )

        with mock.patch(
            "wathiq_araseg.runtime.model_loader._import_torch_module",
            return_value=fake_torch,
        ):
            with self.assertRaises(SmokeInferenceError) as context:
                run_smoke_inference(runtime, "هذا نص عربي تجريبي")

        self.assertIsInstance(context.exception.__cause__, RuntimeError)

    def _load_runtime_with_fakes(
        self,
        *,
        tokenizer: _FakeTokenizer | None = None,
        model: _FakeModel | None = None,
        tokenizer_side_effect=None,
        model_side_effect=None,
    ) -> tuple[LoadedModelRuntime, _FakeTokenizerFactory, _FakeModelFactory]:
        manifest = _build_manifest()
        tokenizer_factory = _FakeTokenizerFactory(
            tokenizer=tokenizer,
            side_effect=tokenizer_side_effect,
        )
        model_factory = _FakeModelFactory(
            model=model,
            side_effect=model_side_effect,
        )
        dependencies = _RuntimeDependencies(
            torch_module=_FakeTorchModule(),
            auto_tokenizer=tokenizer_factory,
            auto_model_for_token_classification=model_factory,
        )

        with mock.patch(
            "wathiq_araseg.runtime.model_loader.load_manifest",
            return_value=manifest,
        ), mock.patch(
            "wathiq_araseg.runtime.model_loader.validate_artifact_from_manifest",
            return_value=None,
        ), mock.patch(
            "wathiq_araseg.runtime.model_loader._resolve_validated_artifact_directory",
            return_value=Path("best_model"),
        ), mock.patch(
            "wathiq_araseg.runtime.model_loader._import_runtime_dependencies",
            return_value=dependencies,
        ):
            runtime = load_local_model_runtime(Path("manifest.json"), device="cpu")

        return runtime, tokenizer_factory, model_factory


class _FailingSmokeModel(_FakeModel):
    def __call__(self, **_kwargs) -> types.SimpleNamespace:
        raise RuntimeError("smoke failure")


class RuntimeLoaderIntegrationTests(unittest.TestCase):
    def test_real_pa_runtime_loads_and_smoke_inference_runs(self) -> None:
        manifest_path = SERVICE_ROOT / "models" / "pa" / "manifest.json"
        artifact_root = SERVICE_ROOT / "models" / "pa" / "best_model"

        if not artifact_root.is_dir():
            self.skipTest("Real PA best_model directory is not present locally.")

        manifest = load_local_model_runtime.__globals__["load_manifest"](manifest_path)
        validation_result = validate_artifact_from_manifest(manifest, manifest_path)

        self.assertEqual(validation_result.validated_file_count, 5)
        self.assertEqual(
            validation_result.model_sha256,
            "7d76a8a15a302800b2ba4dfafb3815f50a03370a5b12c7d6734491ac68bfb9d1",
        )

        runtime = load_local_model_runtime(manifest_path, device="cpu")

        self.assertTrue(runtime.tokenizer.is_fast)
        self.assertEqual(len(runtime.tokenizer), 30001)
        self.assertEqual(runtime.model.config.num_labels, 2)
        self.assertFalse(runtime.model.training)

        result = run_smoke_inference(
            runtime,
            "هذا نص عربي تجريبي. هل يعمل النموذج بصورة صحيحة؟",
        )

        self.assertEqual(result.logits_shape[0], 1)
        self.assertEqual(result.logits_shape[-1], 2)
        self.assertEqual(len(result.logits_shape), 3)
        self.assertTrue(result.all_finite)


if __name__ == "__main__":
    unittest.main()
