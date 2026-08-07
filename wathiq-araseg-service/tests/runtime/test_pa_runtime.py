from __future__ import annotations

from dataclasses import replace
import importlib
import inspect
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.artifacts import (  # noqa: E402
    ArtifactValidationError,
    ArtifactValidationResult,
    ComponentArtifactManifest,
    ComponentArtifactValidationResult,
    ComponentEnsembleMetadata,
    ComponentValidationScope,
    InferenceConfig,
    ManifestFileEntry,
    ValidatedBlindResult,
    validate_artifact_manifest,
    validate_component_artifact_manifest,
)
from wathiq_araseg.pa.models import OriginalTokenSequence  # noqa: E402
from wathiq_araseg.pa.pipeline import PAPipeline  # noqa: E402
from wathiq_araseg.pa.postprocessing import postprocess_pa_probabilities  # noqa: E402
from wathiq_araseg.runtime.model_loader import (  # noqa: E402
    LoadedModelRuntime,
    RuntimeConfigurationMismatchError,
    UnsupportedDeviceError,
)
from wathiq_araseg.runtime.pa_runtime import (  # noqa: E402
    BaseRuntimeLoadError,
    InvalidBaseManifestPathError,
    InvalidMicroManifestPathError,
    MicroArtifactValidationError,
    MicroModelLoadError,
    PAPipelineConstructionError,
    PAEngineConstructionError,
    ProductionIdentityMismatchError,
    RuntimeCompatibilityMismatchError,
    build_pa_pipeline,
)
from wathiq_araseg.runtime import pa_runtime as pa_runtime_module  # noqa: E402
from wathiq_araseg.segmentation import (  # noqa: E402
    SegmentationRequest,
    SegmentationToken,
    render_segments_from_token_boundaries,
)
from wathiq_araseg.artifacts.manifest import ArtifactManifest  # noqa: E402


class PARuntimeBuilderUnitTests(unittest.TestCase):
    def test_builder_returns_papipeline_with_cpu_default_and_stable_identity(self) -> None:
        base_manifest_path, micro_manifest_path = _create_manifest_files(self)
        base_runtime = _build_base_runtime()
        micro_manifest = _build_micro_manifest()
        micro_validation = _build_micro_validation()
        fake_micro_model = _FakeTokenClassificationModel()

        with mock.patch.object(
            pa_runtime_module,
            "load_local_model_runtime",
            return_value=base_runtime,
        ) as base_loader, mock.patch.object(
            pa_runtime_module,
            "load_component_manifest",
            return_value=micro_manifest,
        ), mock.patch.object(
            pa_runtime_module,
            "validate_component_artifact_from_manifest",
            return_value=micro_validation,
        ), mock.patch.object(
            pa_runtime_module,
            "_import_micro_model_loader",
            return_value=_FakeModelFactory(fake_micro_model),
        ), mock.patch.object(
            pa_runtime_module,
            "_build_inference_engine",
            return_value=_FakeInferenceEngine(),
        ):
            pipeline = build_pa_pipeline(base_manifest_path, micro_manifest_path)

        self.assertIsInstance(pipeline, PAPipeline)
        self.assertEqual(pipeline.track, "PA")
        self.assertEqual(pipeline.pipeline_id, "pa-current-micro-ensemble-861752")
        base_loader.assert_called_once_with(base_manifest_path, device="cpu")

    def test_builder_requires_existing_manifest_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            existing_manifest = temp_root / "manifest.json"
            existing_manifest.write_text("{}", encoding="utf-8")
            manifest_directory = temp_root / "manifest-dir"
            manifest_directory.mkdir()

            with self.assertRaises(InvalidBaseManifestPathError):
                build_pa_pipeline(temp_root / "missing-base.json", existing_manifest)
            with self.assertRaises(InvalidMicroManifestPathError):
                build_pa_pipeline(existing_manifest, temp_root / "missing-micro.json")
            with self.assertRaises(InvalidBaseManifestPathError):
                build_pa_pipeline(manifest_directory, existing_manifest)
            with self.assertRaises(InvalidBaseManifestPathError):
                build_pa_pipeline(123, existing_manifest)  # type: ignore[arg-type]
            with self.assertRaises(InvalidMicroManifestPathError):
                build_pa_pipeline(existing_manifest, object())  # type: ignore[arg-type]

    def test_builder_accepts_only_cpu_device(self) -> None:
        base_manifest_path, micro_manifest_path = _create_manifest_files(self)

        for invalid_device in ("", "cuda", " gpu ", True, 123):  # type: ignore[list-item]
            with self.subTest(invalid_device=invalid_device):
                with self.assertRaises(UnsupportedDeviceError):
                    build_pa_pipeline(
                        base_manifest_path,
                        micro_manifest_path,
                        device=invalid_device,  # type: ignore[arg-type]
                    )

    def test_base_runtime_loading_uses_explicit_manifest_once(self) -> None:
        base_manifest_path, micro_manifest_path = _create_manifest_files(self)
        base_runtime = _build_base_runtime()
        micro_manifest = _build_micro_manifest()
        micro_validation = _build_micro_validation()
        fake_micro_model = _FakeTokenClassificationModel()

        with mock.patch.object(
            pa_runtime_module,
            "load_local_model_runtime",
            return_value=base_runtime,
        ) as base_loader, mock.patch.object(
            pa_runtime_module,
            "load_component_manifest",
            return_value=micro_manifest,
        ), mock.patch.object(
            pa_runtime_module,
            "validate_component_artifact_from_manifest",
            return_value=micro_validation,
        ), mock.patch.object(
            pa_runtime_module,
            "_import_micro_model_loader",
            return_value=_FakeModelFactory(fake_micro_model),
        ), mock.patch.object(
            pa_runtime_module,
            "_build_inference_engine",
            return_value=_FakeInferenceEngine(),
        ):
            build_pa_pipeline(base_manifest_path, micro_manifest_path, device="cpu")

        base_loader.assert_called_once_with(base_manifest_path, device="cpu")

    def test_micro_validation_runs_before_micro_model_loading(self) -> None:
        base_manifest_path, micro_manifest_path = _create_manifest_files(self)
        events: list[str] = []
        base_runtime = _build_base_runtime()
        micro_manifest = _build_micro_manifest()
        micro_validation = _build_micro_validation()
        model_factory = _FakeModelFactory(_FakeTokenClassificationModel(), events=events)

        def validating_side_effect(*_args, **_kwargs):
            events.append("validate")
            return micro_validation

        with mock.patch.object(
            pa_runtime_module,
            "load_local_model_runtime",
            return_value=base_runtime,
        ), mock.patch.object(
            pa_runtime_module,
            "load_component_manifest",
            return_value=micro_manifest,
        ), mock.patch.object(
            pa_runtime_module,
            "validate_component_artifact_from_manifest",
            side_effect=validating_side_effect,
        ), mock.patch.object(
            pa_runtime_module,
            "_import_micro_model_loader",
            return_value=model_factory,
        ), mock.patch.object(
            pa_runtime_module,
            "_build_inference_engine",
            return_value=_FakeInferenceEngine(),
        ):
            build_pa_pipeline(base_manifest_path, micro_manifest_path)

        self.assertEqual(events, ["validate", "model"])

    def test_micro_validation_failure_prevents_model_loading(self) -> None:
        base_manifest_path, micro_manifest_path = _create_manifest_files(self)
        base_runtime = _build_base_runtime()
        micro_manifest = _build_micro_manifest()
        model_factory = _FakeModelFactory(_FakeTokenClassificationModel())

        with mock.patch.object(
            pa_runtime_module,
            "load_local_model_runtime",
            return_value=base_runtime,
        ), mock.patch.object(
            pa_runtime_module,
            "load_component_manifest",
            return_value=micro_manifest,
        ), mock.patch.object(
            pa_runtime_module,
            "validate_component_artifact_from_manifest",
            side_effect=ArtifactValidationError("bad micro artifact"),
        ), mock.patch.object(
            pa_runtime_module,
            "_import_micro_model_loader",
            return_value=model_factory,
        ):
            with self.assertRaises(MicroArtifactValidationError):
                build_pa_pipeline(base_manifest_path, micro_manifest_path)

        self.assertEqual(model_factory.calls, [])

    def test_micro_model_loading_is_local_only_and_uses_validated_directory(self) -> None:
        base_manifest_path, micro_manifest_path = _create_manifest_files(self)
        base_runtime = _build_base_runtime()
        micro_manifest = _build_micro_manifest()
        micro_validation = _build_micro_validation()
        fake_micro_model = _FakeTokenClassificationModel()
        model_factory = _FakeModelFactory(fake_micro_model)

        with mock.patch.object(
            pa_runtime_module,
            "load_local_model_runtime",
            return_value=base_runtime,
        ), mock.patch.object(
            pa_runtime_module,
            "load_component_manifest",
            return_value=micro_manifest,
        ), mock.patch.object(
            pa_runtime_module,
            "validate_component_artifact_from_manifest",
            return_value=micro_validation,
        ), mock.patch.object(
            pa_runtime_module,
            "_import_micro_model_loader",
            return_value=model_factory,
        ), mock.patch.object(
            pa_runtime_module,
            "_build_inference_engine",
            return_value=_FakeInferenceEngine(),
        ):
            build_pa_pipeline(base_manifest_path, micro_manifest_path)

        self.assertEqual(len(model_factory.calls), 1)
        self.assertTrue(model_factory.calls[0]["kwargs"]["local_files_only"])
        self.assertEqual(
            Path(model_factory.calls[0]["args"][0]).name,
            "best_model",
        )

    def test_builder_reuses_one_shared_base_tokenizer_for_the_engine(self) -> None:
        base_manifest_path, micro_manifest_path = _create_manifest_files(self)
        base_runtime = _build_base_runtime()
        micro_manifest = _build_micro_manifest()
        micro_validation = _build_micro_validation()
        fake_micro_model = _FakeTokenClassificationModel()
        engine_args: dict[str, object] = {}

        def build_engine(*, tokenizer, base_model, micro_model):
            engine_args["tokenizer"] = tokenizer
            engine_args["base_model"] = base_model
            engine_args["micro_model"] = micro_model
            return _FakeInferenceEngine()

        with mock.patch.object(
            pa_runtime_module,
            "load_local_model_runtime",
            return_value=base_runtime,
        ), mock.patch.object(
            pa_runtime_module,
            "load_component_manifest",
            return_value=micro_manifest,
        ), mock.patch.object(
            pa_runtime_module,
            "validate_component_artifact_from_manifest",
            return_value=micro_validation,
        ), mock.patch.object(
            pa_runtime_module,
            "_import_micro_model_loader",
            return_value=_FakeModelFactory(fake_micro_model),
        ), mock.patch.object(
            pa_runtime_module,
            "_build_inference_engine",
            side_effect=build_engine,
        ):
            build_pa_pipeline(base_manifest_path, micro_manifest_path)

        self.assertIs(engine_args["tokenizer"], base_runtime.tokenizer)
        self.assertIs(engine_args["base_model"], base_runtime.model)
        self.assertIs(engine_args["micro_model"], fake_micro_model)

    def test_builder_keeps_models_on_cpu_and_in_eval_mode(self) -> None:
        base_manifest_path, micro_manifest_path = _create_manifest_files(self)
        base_runtime = _build_base_runtime()
        micro_manifest = _build_micro_manifest()
        micro_validation = _build_micro_validation()
        fake_micro_model = _FakeTokenClassificationModel()

        with mock.patch.object(
            pa_runtime_module,
            "load_local_model_runtime",
            return_value=base_runtime,
        ), mock.patch.object(
            pa_runtime_module,
            "load_component_manifest",
            return_value=micro_manifest,
        ), mock.patch.object(
            pa_runtime_module,
            "validate_component_artifact_from_manifest",
            return_value=micro_validation,
        ), mock.patch.object(
            pa_runtime_module,
            "_import_micro_model_loader",
            return_value=_FakeModelFactory(fake_micro_model),
        ), mock.patch.object(
            pa_runtime_module,
            "_build_inference_engine",
            return_value=_FakeInferenceEngine(),
        ):
            build_pa_pipeline(base_manifest_path, micro_manifest_path)

        self.assertFalse(base_runtime.model.training)
        self.assertFalse(fake_micro_model.training)
        self.assertEqual(base_runtime.model.device, "cpu")
        self.assertEqual(fake_micro_model.device, "cpu")
        self.assertEqual(fake_micro_model.to_calls, ["cpu"])
        self.assertEqual(fake_micro_model.eval_calls, 1)

    def test_builder_rejects_production_identity_drift(self) -> None:
        base_manifest_path, micro_manifest_path = _create_manifest_files(self)
        base_runtime = _build_base_runtime()
        fake_micro_model = _FakeTokenClassificationModel()
        cases = (
            ("track", replace(_build_base_runtime().manifest, track="PB"), _build_micro_manifest(), _build_micro_validation()),
            ("artifact role", base_runtime.manifest, replace(_build_micro_manifest(), artifact_role="standalone"), _build_micro_validation()),
            ("base source run", replace(base_runtime.manifest, source_run="wrong-run"), _build_micro_manifest(), _build_micro_validation()),
            ("micro source run", base_runtime.manifest, replace(_build_micro_manifest(), source_run="wrong-run"), _build_micro_validation()),
            ("board id", base_runtime.manifest, _build_micro_manifest(), replace(_build_micro_validation(), ensemble=replace(_build_micro_validation().ensemble, board_submission_id=1))),
            ("submission file", base_runtime.manifest, _build_micro_manifest(), replace(_build_micro_validation(), ensemble=replace(_build_micro_validation().ensemble, submission_file="wrong.zip"))),
            ("paired base run", base_runtime.manifest, _build_micro_manifest(), replace(_build_micro_validation(), ensemble=replace(_build_micro_validation().ensemble, paired_base_run="wrong"))),
            ("weights", base_runtime.manifest, _build_micro_manifest(), replace(_build_micro_validation(), ensemble=replace(_build_micro_validation().ensemble, micro_weight=0.1))),
            ("max length", base_runtime.manifest, _build_micro_manifest(), replace(_build_micro_validation(), ensemble=replace(_build_micro_validation().ensemble, max_length=256))),
            ("stride", base_runtime.manifest, _build_micro_manifest(), replace(_build_micro_validation(), ensemble=replace(_build_micro_validation().ensemble, stride=32))),
            ("default threshold", base_runtime.manifest, _build_micro_manifest(), replace(_build_micro_validation(), ensemble=replace(_build_micro_validation().ensemble, default_threshold=0.4))),
            ("punctuation threshold", base_runtime.manifest, _build_micro_manifest(), replace(_build_micro_validation(), ensemble=replace(_build_micro_validation().ensemble, punctuation_threshold=0.2))),
            ("validation scope", base_runtime.manifest, _build_micro_manifest(), replace(_build_micro_validation(), validation_scope=replace(_build_micro_validation().validation_scope, board_validation_scope="standalone"))),
            ("standalone score", base_runtime.manifest, _build_micro_manifest(), replace(_build_micro_validation(), validation_scope=replace(_build_micro_validation().validation_scope, standalone_component_score_asserted=True))),
        )

        for name, base_manifest, micro_manifest, micro_validation in cases:
            with self.subTest(name=name):
                drifted_base_runtime = replace(base_runtime, manifest=base_manifest)

                with mock.patch.object(
                    pa_runtime_module,
                    "load_local_model_runtime",
                    return_value=drifted_base_runtime,
                ), mock.patch.object(
                    pa_runtime_module,
                    "load_component_manifest",
                    return_value=micro_manifest,
                ), mock.patch.object(
                    pa_runtime_module,
                    "validate_component_artifact_from_manifest",
                    return_value=micro_validation,
                ), mock.patch.object(
                    pa_runtime_module,
                    "_import_micro_model_loader",
                    return_value=_FakeModelFactory(fake_micro_model),
                ), mock.patch.object(
                    pa_runtime_module,
                    "_build_inference_engine",
                    return_value=_FakeInferenceEngine(),
                ):
                    with self.assertRaises(ProductionIdentityMismatchError):
                        build_pa_pipeline(base_manifest_path, micro_manifest_path)

    def test_builder_rejects_runtime_compatibility_mismatches(self) -> None:
        base_manifest_path, micro_manifest_path = _create_manifest_files(self)
        micro_manifest = _build_micro_manifest()
        micro_validation = _build_micro_validation()
        cases = (
            (
                "tokenizer class",
                _build_base_runtime(tokenizer=OtherTokenizer()),
                _FakeTokenClassificationModel(),
            ),
            (
                "tokenizer vocabulary",
                _build_base_runtime(tokenizer=BertTokenizerFast(vocab_size=123)),
                _FakeTokenClassificationModel(vocab_size=123),
            ),
            (
                "micro architecture",
                _build_base_runtime(),
                _FakeTokenClassificationModel(architecture="OtherArchitecture"),
            ),
            (
                "micro label count",
                _build_base_runtime(),
                _FakeTokenClassificationModel(num_labels=3),
            ),
            (
                "micro vocabulary",
                _build_base_runtime(),
                _FakeTokenClassificationModel(vocab_size=123),
            ),
        )

        for name, base_runtime, micro_model in cases:
            with self.subTest(name=name):
                with mock.patch.object(
                    pa_runtime_module,
                    "load_local_model_runtime",
                    return_value=base_runtime,
                ), mock.patch.object(
                    pa_runtime_module,
                    "load_component_manifest",
                    return_value=micro_manifest,
                ), mock.patch.object(
                    pa_runtime_module,
                    "validate_component_artifact_from_manifest",
                    return_value=micro_validation,
                ), mock.patch.object(
                    pa_runtime_module,
                    "_import_micro_model_loader",
                    return_value=_FakeModelFactory(micro_model),
                ), mock.patch.object(
                    pa_runtime_module,
                    "_build_inference_engine",
                    return_value=_FakeInferenceEngine(),
                ):
                    with self.assertRaises(RuntimeCompatibilityMismatchError):
                        build_pa_pipeline(base_manifest_path, micro_manifest_path)

    def test_builder_stages_failures_with_chained_causes(self) -> None:
        base_manifest_path, micro_manifest_path = _create_manifest_files(self)
        base_runtime = _build_base_runtime()
        micro_manifest = _build_micro_manifest()
        micro_validation = _build_micro_validation()
        fake_micro_model = _FakeTokenClassificationModel()

        with mock.patch.object(
            pa_runtime_module,
            "load_local_model_runtime",
            side_effect=RuntimeConfigurationMismatchError("bad base"),
        ):
            with self.assertRaises(BaseRuntimeLoadError) as raised:
                build_pa_pipeline(base_manifest_path, micro_manifest_path)
        self.assertIsInstance(raised.exception.__cause__, RuntimeConfigurationMismatchError)

        with mock.patch.object(
            pa_runtime_module,
            "load_local_model_runtime",
            return_value=base_runtime,
        ), mock.patch.object(
            pa_runtime_module,
            "load_component_manifest",
            return_value=micro_manifest,
        ), mock.patch.object(
            pa_runtime_module,
            "validate_component_artifact_from_manifest",
            side_effect=ArtifactValidationError("bad micro"),
        ):
            with self.assertRaises(MicroArtifactValidationError) as raised:
                build_pa_pipeline(base_manifest_path, micro_manifest_path)
        self.assertIsInstance(raised.exception.__cause__, ArtifactValidationError)

        with mock.patch.object(
            pa_runtime_module,
            "load_local_model_runtime",
            return_value=base_runtime,
        ), mock.patch.object(
            pa_runtime_module,
            "load_component_manifest",
            return_value=micro_manifest,
        ), mock.patch.object(
            pa_runtime_module,
            "validate_component_artifact_from_manifest",
            return_value=micro_validation,
        ), mock.patch.object(
            pa_runtime_module,
            "_import_micro_model_loader",
            return_value=_FakeModelFactory(side_effect=OSError("micro load failure")),
        ):
            with self.assertRaises(MicroModelLoadError) as raised:
                build_pa_pipeline(base_manifest_path, micro_manifest_path)
        self.assertIsInstance(raised.exception.__cause__, OSError)

        with mock.patch.object(
            pa_runtime_module,
            "load_local_model_runtime",
            return_value=_build_base_runtime(tokenizer=OtherTokenizer()),
        ), mock.patch.object(
            pa_runtime_module,
            "load_component_manifest",
            return_value=micro_manifest,
        ), mock.patch.object(
            pa_runtime_module,
            "validate_component_artifact_from_manifest",
            return_value=micro_validation,
        ), mock.patch.object(
            pa_runtime_module,
            "_import_micro_model_loader",
            return_value=_FakeModelFactory(fake_micro_model),
        ):
            with self.assertRaises(RuntimeCompatibilityMismatchError):
                build_pa_pipeline(base_manifest_path, micro_manifest_path)

        with mock.patch.object(
            pa_runtime_module,
            "load_local_model_runtime",
            return_value=base_runtime,
        ), mock.patch.object(
            pa_runtime_module,
            "load_component_manifest",
            return_value=micro_manifest,
        ), mock.patch.object(
            pa_runtime_module,
            "validate_component_artifact_from_manifest",
            return_value=micro_validation,
        ), mock.patch.object(
            pa_runtime_module,
            "_import_micro_model_loader",
            return_value=_FakeModelFactory(fake_micro_model),
        ), mock.patch.object(
            pa_runtime_module,
            "_build_inference_engine",
            side_effect=PAEngineConstructionError("engine failure"),
        ):
            with self.assertRaises(PAEngineConstructionError):
                build_pa_pipeline(base_manifest_path, micro_manifest_path)

        with mock.patch.object(
            pa_runtime_module,
            "load_local_model_runtime",
            return_value=base_runtime,
        ), mock.patch.object(
            pa_runtime_module,
            "load_component_manifest",
            return_value=micro_manifest,
        ), mock.patch.object(
            pa_runtime_module,
            "validate_component_artifact_from_manifest",
            return_value=micro_validation,
        ), mock.patch.object(
            pa_runtime_module,
            "_import_micro_model_loader",
            return_value=_FakeModelFactory(fake_micro_model),
        ), mock.patch.object(
            pa_runtime_module,
            "_build_inference_engine",
            return_value=_FakeInferenceEngine(),
        ), mock.patch.object(
            pa_runtime_module,
            "_build_pipeline",
            side_effect=PAPipelineConstructionError("pipeline failure"),
        ):
            with self.assertRaises(PAPipelineConstructionError):
                build_pa_pipeline(base_manifest_path, micro_manifest_path)

    def test_runtime_imports_do_not_trigger_loading_or_validation(self) -> None:
        runtime_module_name = "wathiq_araseg.runtime"
        builder_module_name = "wathiq_araseg.runtime.pa_runtime"
        sys.modules.pop(runtime_module_name, None)
        sys.modules.pop(builder_module_name, None)

        with mock.patch(
            "wathiq_araseg.runtime.model_loader.load_local_model_runtime"
        ) as base_loader, mock.patch(
            "wathiq_araseg.artifacts.load_component_manifest"
        ) as component_loader, mock.patch(
            "wathiq_araseg.artifacts.validate_component_artifact_from_manifest"
        ) as component_validator:
            importlib.import_module(runtime_module_name)

        base_loader.assert_not_called()
        component_loader.assert_not_called()
        component_validator.assert_not_called()

    def test_builder_source_contains_no_registration_or_tokenization_logic(self) -> None:
        source = inspect.getsource(pa_runtime_module)

        for forbidden_snippet in (
            "FastAPI",
            "PipelineRegistry",
            "SentenceSegmentationService",
            "app.py",
            "split(",
            "splitlines(",
            "AutoTokenizer",
            "hf_hub_download",
            "snapshot_download",
        ):
            with self.subTest(forbidden_snippet=forbidden_snippet):
                self.assertNotIn(forbidden_snippet, source)


class PARuntimeBuilderRealIntegrationTests(unittest.TestCase):
    def test_real_builder_constructs_working_pipeline_offline(self) -> None:
        base_manifest_path = SERVICE_ROOT / "models" / "pa" / "manifest.json"
        micro_manifest_path = SERVICE_ROOT / "models" / "pa" / "micro" / "manifest.json"
        base_artifact_root = SERVICE_ROOT / "models" / "pa" / "best_model"
        micro_artifact_root = SERVICE_ROOT / "models" / "pa" / "micro" / "best_model"

        if not base_artifact_root.is_dir() or not micro_artifact_root.is_dir():
            self.skipTest("Local PA base or micro best_model directory is not present.")

        base_validation = validate_artifact_manifest(base_manifest_path)
        micro_validation = validate_component_artifact_manifest(micro_manifest_path)

        self.assertEqual(base_validation.validated_file_count, 5)
        self.assertEqual(micro_validation.validated_file_count, 5)
        self.assertEqual(
            base_validation.model_sha256,
            "7d76a8a15a302800b2ba4dfafb3815f50a03370a5b12c7d6734491ac68bfb9d1",
        )
        self.assertEqual(
            micro_validation.model_sha256,
            "af194bf0b31823febd1f9479f771fe29409751561f56205dec03358ab38eb9f3",
        )

        start_time = time.perf_counter()
        pipeline = build_pa_pipeline(
            base_manifest_path,
            micro_manifest_path,
            device="cpu",
        )
        build_duration = time.perf_counter() - start_time

        self.assertIsInstance(pipeline, PAPipeline)
        self.assertEqual(pipeline.track, "PA")
        self.assertEqual(pipeline.pipeline_id, "pa-current-micro-ensemble-861752")
        self.assertGreater(build_duration, 0.0)

        request = _build_real_tokenized_request()
        first = pipeline.segment(request)
        second = pipeline.segment(request)

        self.assertEqual(first, second)
        self.assertEqual(first.document_id, "doc-runtime")
        self.assertEqual(first.track, "PA")
        self.assertEqual(first.pipeline_id, "pa-current-micro-ensemble-861752")
        self.assertEqual(first.normalized_text, request.text)
        self.assertTrue(all(segment.text != "" for segment in first.segments))
        self.assertEqual("".join(segment.text for segment in first.segments), request.text)
        self.assertIn("\n", "".join(segment.text for segment in first.segments))
        self.assertIn("\\n", "".join(segment.text for segment in first.segments))
        self.assertIn("[PAR]", "".join(segment.text for segment in first.segments))

        engine = pipeline._inference_engine
        self.assertFalse(engine._base_model.training)
        self.assertFalse(engine._micro_model.training)

        original_tokens = OriginalTokenSequence(tuple(token.text for token in request.tokens or ()))
        probability_result = engine.infer_probabilities(original_tokens)
        postprocessing_result = postprocess_pa_probabilities(probability_result)
        boundary_indices = tuple(
            decision.token_index
            for decision in postprocessing_result.decisions
            if decision.is_boundary
        )
        reference_segments = render_segments_from_token_boundaries(
            normalized_text=request.text,
            tokens=request.tokens or (),
            boundary_token_indices=boundary_indices,
        )

        self.assertEqual(
            tuple(segment.text for segment in first.segments),
            reference_segments,
        )


class _FakeInferenceEngine:
    def infer_probabilities(self, original_tokens: OriginalTokenSequence):
        return types.SimpleNamespace(original_tokens=original_tokens)


class BertTokenizerFast:
    def __init__(self, *, vocab_size: int = 30001) -> None:
        self._vocab_size = vocab_size

    def __len__(self) -> int:
        return self._vocab_size


class OtherTokenizer:
    def __init__(self, *, vocab_size: int = 30001) -> None:
        self._vocab_size = vocab_size

    def __len__(self) -> int:
        return self._vocab_size


class _FakeTokenClassificationModel:
    def __init__(
        self,
        *,
        architecture: str = "BertForTokenClassification",
        num_labels: int = 2,
        vocab_size: int = 30001,
    ) -> None:
        self.config = types.SimpleNamespace(
            architectures=[architecture],
            num_labels=num_labels,
            vocab_size=vocab_size,
        )
        self.device = "cpu"
        self.training = False
        self.to_calls: list[str] = []
        self.eval_calls = 0

    def to(self, device: str) -> _FakeTokenClassificationModel:
        self.device = device
        self.to_calls.append(device)
        return self

    def eval(self) -> _FakeTokenClassificationModel:
        self.training = False
        self.eval_calls += 1
        return self


class _FakeModelFactory:
    def __init__(
        self,
        model: _FakeTokenClassificationModel | None = None,
        *,
        side_effect: Exception | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.model = model or _FakeTokenClassificationModel()
        self.side_effect = side_effect
        self.events = events
        self.calls: list[dict[str, object]] = []

    def from_pretrained(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        if self.events is not None:
            self.events.append("model")
        if self.side_effect is not None:
            raise self.side_effect
        return self.model


def _create_manifest_files(test_case: unittest.TestCase) -> tuple[Path, Path]:
    temp_dir = tempfile.TemporaryDirectory()
    test_case.addCleanup(temp_dir.cleanup)
    temp_root = Path(temp_dir.name)
    base_manifest_path = temp_root / "manifest.json"
    micro_manifest_path = temp_root / "micro-manifest.json"
    (temp_root / "best_model").mkdir()
    base_manifest_path.write_text("{}", encoding="utf-8")
    micro_manifest_path.write_text("{}", encoding="utf-8")
    return base_manifest_path, micro_manifest_path


def _build_base_runtime(
    *,
    tokenizer=None,
    model: _FakeTokenClassificationModel | None = None,
    manifest: ArtifactManifest | None = None,
) -> LoadedModelRuntime:
    runtime_model = model or _FakeTokenClassificationModel()
    return LoadedModelRuntime(
        tokenizer=tokenizer or BertTokenizerFast(),
        model=runtime_model,
        device="cpu",
        manifest=manifest or _build_base_manifest(),
        artifact_directory=Path("best_model"),
    )


def _build_base_manifest() -> ArtifactManifest:
    return ArtifactManifest(
        schema_version="1.0",
        provider="AraSeg",
        track="PA",
        model_version="PA_finetune_20260723_104427",
        source_run="PA_finetune_20260723_104427",
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


def _build_micro_manifest() -> ComponentArtifactManifest:
    return ComponentArtifactManifest(
        schema_version="1.0",
        provider="AraSeg",
        track="PA",
        artifact_role="micro-ensemble-member",
        model_version="PA_micro_20260724_174832",
        source_run="PA_micro_20260724_174832",
        artifact_directory="best_model",
        model_file="model.safetensors",
        model_sha256="af194bf0b31823febd1f9479f771fe29409751561f56205dec03358ab38eb9f3",
        architecture="BertForTokenClassification",
        tokenizer_class="BertTokenizer",
        number_of_labels=2,
        vocabulary_size=30001,
        validation_scope=_build_validation_scope(),
        ensemble=_build_ensemble_metadata(),
        files={
            "model.safetensors": ManifestFileEntry(
                size_bytes=1,
                sha256="af194bf0b31823febd1f9479f771fe29409751561f56205dec03358ab38eb9f3",
            ),
        },
    )


def _build_validation_scope() -> ComponentValidationScope:
    return ComponentValidationScope(
        artifact_integrity="validated",
        compatibility_metadata="validated",
        board_validation_scope="ensemble-only",
        standalone_component_score_asserted=False,
    )


def _build_ensemble_metadata() -> ComponentEnsembleMetadata:
    return ComponentEnsembleMetadata(
        board_submission_id=861752,
        submission_file="pa_current_micro_ens_a095_m005_d0543_e0310.zip",
        paired_base_run="PA_finetune_20260723_104427",
        base_weight=0.95,
        micro_weight=0.05,
        max_length=512,
        stride=64,
        default_threshold=0.543,
        punctuation_threshold=0.31,
    )


def _build_micro_validation() -> ComponentArtifactValidationResult:
    return ComponentArtifactValidationResult(
        track="PA",
        artifact_role="micro-ensemble-member",
        model_version="PA_micro_20260724_174832",
        source_run="PA_micro_20260724_174832",
        artifact_directory="best_model",
        model_file="model.safetensors",
        model_sha256="af194bf0b31823febd1f9479f771fe29409751561f56205dec03358ab38eb9f3",
        validation_scope=_build_validation_scope(),
        ensemble=_build_ensemble_metadata(),
        validated_files=(
            "config.json",
            "model.safetensors",
            "tokenizer.json",
            "tokenizer_config.json",
            "training_args.bin",
        ),
    )


def _build_real_tokenized_request() -> SegmentationRequest:
    source = "  هذا .\tنص\n\\n[PAR]!  "
    tokens = (
        SegmentationToken(index=0, text="هذا", start_offset=2, end_offset=5),
        SegmentationToken(index=1, text=".", start_offset=6, end_offset=7),
        SegmentationToken(index=2, text="نص", start_offset=8, end_offset=10),
        SegmentationToken(index=3, text="\n", start_offset=10, end_offset=11),
        SegmentationToken(index=4, text="\\n", start_offset=11, end_offset=13),
        SegmentationToken(index=5, text="[PAR]", start_offset=13, end_offset=18),
        SegmentationToken(index=6, text="!", start_offset=18, end_offset=19),
    )
    return SegmentationRequest(
        document_id="doc-runtime",
        text=source,
        track="PA",
        tokens=tokens,
    )


if __name__ == "__main__":
    unittest.main()
