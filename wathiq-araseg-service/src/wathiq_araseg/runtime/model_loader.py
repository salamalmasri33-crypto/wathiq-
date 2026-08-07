"""Offline local model loading and smoke inference for the PA artifact."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
from typing import Any

from wathiq_araseg.artifacts import (
    ArtifactManifest,
    load_manifest,
    validate_artifact_from_manifest,
)


class ModelRuntimeError(Exception):
    """Base exception for local runtime loading and smoke inference."""


class RuntimeDependencyError(ModelRuntimeError):
    """Raised when required runtime dependencies are unavailable."""


class UnsupportedDeviceError(ModelRuntimeError):
    """Raised when the requested runtime device is not supported."""


class ArtifactResolutionError(ModelRuntimeError):
    """Raised when a validated artifact directory cannot be resolved safely."""


class TokenizerLoadError(ModelRuntimeError):
    """Raised when the local tokenizer cannot be loaded safely."""


class ModelLoadError(ModelRuntimeError):
    """Raised when the local token-classification model cannot be loaded safely."""


class RuntimeConfigurationMismatchError(ModelRuntimeError):
    """Raised when loaded runtime metadata disagrees with the validated manifest."""


class SmokeInferenceError(ModelRuntimeError):
    """Raised when local smoke inference cannot complete safely."""


@dataclass(frozen=True, slots=True)
class LoadedModelRuntime:
    """Loaded local runtime for the validated PA artifact."""

    tokenizer: Any
    model: Any
    device: str
    manifest: ArtifactManifest
    artifact_directory: Path


@dataclass(frozen=True, slots=True)
class SmokeInferenceResult:
    """Safe metadata returned from local smoke inference."""

    input_token_count: int
    logits_shape: tuple[int, ...]
    number_of_labels: int
    all_finite: bool


@dataclass(frozen=True, slots=True)
class _RuntimeDependencies:
    torch_module: Any
    auto_tokenizer: Any
    auto_model_for_token_classification: Any


def load_local_model_runtime(
    manifest_path: Path,
    device: str = "cpu",
) -> LoadedModelRuntime:
    """Load the validated local PA runtime without any network access."""

    normalized_device = _normalize_device(device)
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)
    validate_artifact_from_manifest(manifest, manifest_path)
    artifact_directory = _resolve_validated_artifact_directory(
        manifest_path,
        manifest.artifact_directory,
    )
    dependencies = _import_runtime_dependencies()

    tokenizer = _load_local_tokenizer(dependencies, artifact_directory)
    model = _load_local_model(dependencies, artifact_directory, normalized_device)
    _validate_loaded_runtime(manifest, tokenizer, model)

    return LoadedModelRuntime(
        tokenizer=tokenizer,
        model=model,
        device=normalized_device,
        manifest=manifest,
        artifact_directory=artifact_directory,
    )


def run_smoke_inference(
    runtime: LoadedModelRuntime,
    sample_text: str,
) -> SmokeInferenceResult:
    """Run a minimal offline smoke inference and return only safe metadata."""

    if not isinstance(sample_text, str) or not sample_text.strip():
        raise SmokeInferenceError("Smoke inference sample text must be a non-empty string.")

    torch_module = _import_torch_module()

    try:
        encoded_inputs = runtime.tokenizer(
            sample_text,
            truncation=True,
            max_length=runtime.manifest.inference.max_length,
            return_tensors="pt",
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise SmokeInferenceError("Unable to tokenize smoke inference input.") from exc

    try:
        moved_inputs = {
            key: value.to(runtime.device)
            for key, value in encoded_inputs.items()
        }
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise SmokeInferenceError(
            "Unable to move smoke inference tensors to the configured device."
        ) from exc

    input_ids = moved_inputs.get("input_ids")
    if input_ids is None:
        raise SmokeInferenceError("Smoke inference inputs must include input_ids.")

    try:
        with torch_module.inference_mode():
            outputs = runtime.model(**moved_inputs)
            logits = outputs.logits
            logits_shape = tuple(int(dimension) for dimension in logits.shape)
            all_finite = bool(torch_module.isfinite(logits).all().item())
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise SmokeInferenceError("Unable to execute smoke inference.") from exc

    try:
        input_token_count = int(input_ids.shape[-1])
    except (AttributeError, IndexError, TypeError, ValueError) as exc:
        raise SmokeInferenceError("Unable to determine smoke inference token count.") from exc

    number_of_labels = logits_shape[-1] if logits_shape else 0

    return SmokeInferenceResult(
        input_token_count=input_token_count,
        logits_shape=logits_shape,
        number_of_labels=number_of_labels,
        all_finite=all_finite,
    )


def _normalize_device(device: str) -> str:
    if not isinstance(device, str) or not device.strip():
        raise UnsupportedDeviceError("Runtime device must be a non-empty string.")

    normalized_device = device.strip().lower()
    if normalized_device != "cpu":
        raise UnsupportedDeviceError(
            f"Unsupported runtime device '{device}'. Only 'cpu' is currently supported."
        )

    return normalized_device


def _import_runtime_dependencies() -> _RuntimeDependencies:
    torch_module = _import_torch_module()

    try:
        transformers_module = importlib.import_module("transformers")
    except ImportError as exc:
        raise RuntimeDependencyError(
            "Transformers runtime dependencies are not installed."
        ) from exc

    return _RuntimeDependencies(
        torch_module=torch_module,
        auto_tokenizer=transformers_module.AutoTokenizer,
        auto_model_for_token_classification=transformers_module.AutoModelForTokenClassification,
    )


def _import_torch_module() -> Any:
    try:
        return importlib.import_module("torch")
    except ImportError as exc:
        raise RuntimeDependencyError("PyTorch runtime dependencies are not installed.") from exc


def _resolve_validated_artifact_directory(
    manifest_path: Path,
    artifact_directory: str,
) -> Path:
    try:
        manifest_directory = manifest_path.resolve(strict=True).parent
    except FileNotFoundError as exc:
        raise ArtifactResolutionError("Validated manifest path could not be resolved.") from exc
    except OSError as exc:
        raise ArtifactResolutionError("Unable to inspect the validated manifest path.") from exc

    try:
        resolved_artifact_directory = (manifest_directory / artifact_directory).resolve(strict=True)
    except FileNotFoundError as exc:
        raise ArtifactResolutionError("Validated artifact directory is not available locally.") from exc
    except OSError as exc:
        raise ArtifactResolutionError("Unable to resolve the validated artifact directory.") from exc

    try:
        resolved_artifact_directory.relative_to(manifest_directory)
    except ValueError as exc:
        raise ArtifactResolutionError(
            "Validated artifact directory must remain inside the manifest directory."
        ) from exc

    return resolved_artifact_directory


def _load_local_tokenizer(
    dependencies: _RuntimeDependencies,
    artifact_directory: Path,
) -> Any:
    try:
        return dependencies.auto_tokenizer.from_pretrained(
            str(artifact_directory),
            local_files_only=True,
            use_fast=True,
            trust_remote_code=False,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise TokenizerLoadError("Unable to load the local tokenizer artifact.") from exc


def _load_local_model(
    dependencies: _RuntimeDependencies,
    artifact_directory: Path,
    device: str,
) -> Any:
    try:
        model = dependencies.auto_model_for_token_classification.from_pretrained(
            str(artifact_directory),
            local_files_only=True,
            trust_remote_code=False,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ModelLoadError("Unable to load the local token-classification model.") from exc

    try:
        model = model.to(device)
        model.eval()
    except (RuntimeError, TypeError, ValueError) as exc:
        raise ModelLoadError(
            "Unable to prepare the local model on the requested device."
        ) from exc

    return model


def _validate_loaded_runtime(
    manifest: ArtifactManifest,
    tokenizer: Any,
    model: Any,
) -> None:
    tokenizer_vocabulary_size = _get_tokenizer_vocabulary_size(tokenizer)
    if tokenizer_vocabulary_size != manifest.vocabulary_size:
        raise RuntimeConfigurationMismatchError(
            "Loaded tokenizer vocabulary size does not match the validated manifest."
        )

    model_label_count = getattr(getattr(model, "config", None), "num_labels", None)
    if model_label_count != manifest.number_of_labels:
        raise RuntimeConfigurationMismatchError(
            "Loaded model label count does not match the validated manifest."
        )

    if getattr(model, "training", None) is not False:
        raise RuntimeConfigurationMismatchError(
            "Loaded model must be placed into evaluation mode before use."
        )


def _get_tokenizer_vocabulary_size(tokenizer: Any) -> Any:
    try:
        return len(tokenizer)
    except (AttributeError, TypeError):
        return getattr(tokenizer, "vocab_size", None)
