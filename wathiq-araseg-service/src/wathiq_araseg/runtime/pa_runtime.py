"""Production-local runtime composition for the selected PA ensemble pipeline."""

from __future__ import annotations

import importlib
import math
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any

from wathiq_araseg.artifacts import (
    ArtifactValidationError,
    ComponentArtifactManifest,
    ComponentArtifactValidationResult,
    ComponentManifestError,
    ManifestError,
    load_component_manifest,
    validate_component_artifact_from_manifest,
)

from .model_loader import (
    LoadedModelRuntime,
    ModelRuntimeError,
    RuntimeConfigurationMismatchError,
    UnsupportedDeviceError,
    load_local_model_runtime,
)

if TYPE_CHECKING:
    from wathiq_araseg.pa.pipeline import PAPipeline


class PARuntimeBuilderError(ModelRuntimeError):
    """Base exception for composing the production-local PA runtime."""


class InvalidBaseManifestPathError(PARuntimeBuilderError):
    """Raised when the base manifest path input is missing or malformed."""


class InvalidMicroManifestPathError(PARuntimeBuilderError):
    """Raised when the micro manifest path input is missing or malformed."""


class BaseRuntimeLoadError(PARuntimeBuilderError):
    """Raised when the validated base runtime cannot be loaded locally."""


class MicroArtifactValidationError(PARuntimeBuilderError):
    """Raised when the micro component artifact cannot be validated locally."""


class ProductionIdentityMismatchError(PARuntimeBuilderError):
    """Raised when manifest metadata drifts from the selected PA production identity."""


class RuntimeCompatibilityMismatchError(PARuntimeBuilderError):
    """Raised when the base runtime, micro model, and shared tokenizer are incompatible."""


class MicroModelLoadError(PARuntimeBuilderError):
    """Raised when the validated local micro model cannot be loaded safely."""


class PAEngineConstructionError(PARuntimeBuilderError):
    """Raised when the PA ensemble inference engine cannot be constructed safely."""


class PAPipelineConstructionError(PARuntimeBuilderError):
    """Raised when the production PAPipeline cannot be constructed safely."""


_SUPPORTED_DEVICE = "cpu"
_EXPECTED_TRACK = "PA"
_EXPECTED_ARTIFACT_ROLE = "micro-ensemble-member"
_EXPECTED_BASE_SOURCE_RUN = "PA_finetune_20260723_104427"
_EXPECTED_MICRO_SOURCE_RUN = "PA_micro_20260724_174832"
_EXPECTED_BOARD_SUBMISSION_ID = 861752
_EXPECTED_SUBMISSION_FILE = "pa_current_micro_ens_a095_m005_d0543_e0310.zip"
_EXPECTED_BASE_MODEL_SHA256 = "7d76a8a15a302800b2ba4dfafb3815f50a03370a5b12c7d6734491ac68bfb9d1"
_EXPECTED_MICRO_MODEL_SHA256 = "af194bf0b31823febd1f9479f771fe29409751561f56205dec03358ab38eb9f3"
_EXPECTED_ARCHITECTURE = "BertForTokenClassification"
_EXPECTED_TOKENIZER_CLASS = "BertTokenizer"
_EXPECTED_LABEL_COUNT = 2
_EXPECTED_VOCABULARY_SIZE = 30001
_WEIGHT_TOLERANCE = 1e-12


def build_pa_pipeline(
    base_manifest_path: Path,
    micro_manifest_path: Path,
    *,
    device: str = _SUPPORTED_DEVICE,
) -> PAPipeline:
    """Build the validated production-local PAPipeline without any runtime wiring."""

    validated_base_manifest_path = _coerce_manifest_path(
        base_manifest_path,
        error_type=InvalidBaseManifestPathError,
    )
    validated_micro_manifest_path = _coerce_manifest_path(
        micro_manifest_path,
        error_type=InvalidMicroManifestPathError,
    )
    normalized_device = _normalize_builder_device(device)

    base_runtime = _load_validated_base_runtime(
        validated_base_manifest_path,
        normalized_device,
    )
    micro_manifest = _load_validated_micro_manifest(validated_micro_manifest_path)
    micro_validation = _validate_micro_component_artifact(
        micro_manifest,
        validated_micro_manifest_path,
    )
    micro_artifact_directory = _resolve_validated_artifact_directory(
        validated_micro_manifest_path,
        micro_validation.artifact_directory,
    )

    _validate_selected_production_identity(
        base_runtime,
        micro_manifest,
        micro_validation,
    )

    micro_model = _load_validated_micro_model(
        micro_artifact_directory,
        normalized_device,
    )
    _validate_runtime_compatibility(
        base_runtime,
        micro_manifest,
        micro_validation,
        micro_model,
    )

    inference_engine = _build_inference_engine(
        tokenizer=base_runtime.tokenizer,
        base_model=base_runtime.model,
        micro_model=micro_model,
    )
    return _build_pipeline(inference_engine)


def _coerce_manifest_path(
    manifest_path: Path | PathLike[str] | str,
    *,
    error_type: type[PARuntimeBuilderError],
) -> Path:
    if isinstance(manifest_path, bool):
        raise error_type("Manifest inputs must use a manifest file path.")

    try:
        normalized_path = Path(manifest_path)
    except (TypeError, ValueError) as exc:
        raise error_type("Manifest inputs must use a manifest file path.") from exc

    if not normalized_path.exists():
        raise error_type("Manifest inputs must point to an existing manifest file.")
    if not normalized_path.is_file():
        raise error_type("Manifest inputs must point to a manifest file, not a directory.")

    return normalized_path


def _normalize_builder_device(device: str) -> str:
    if not isinstance(device, str) or not device.strip():
        raise UnsupportedDeviceError("Runtime device must be a non-empty string.")

    normalized_device = device.strip().lower()
    if normalized_device != _SUPPORTED_DEVICE:
        raise UnsupportedDeviceError(
            f"Unsupported runtime device '{device}'. Only 'cpu' is currently supported."
        )

    return normalized_device


def _load_validated_base_runtime(
    manifest_path: Path,
    device: str,
) -> LoadedModelRuntime:
    try:
        return load_local_model_runtime(manifest_path, device=device)
    except (ArtifactValidationError, ManifestError, ModelRuntimeError) as exc:
        raise BaseRuntimeLoadError(
            "Unable to load the validated local PA base runtime."
        ) from exc


def _load_validated_micro_manifest(manifest_path: Path) -> ComponentArtifactManifest:
    try:
        return load_component_manifest(manifest_path)
    except ComponentManifestError as exc:
        raise InvalidMicroManifestPathError(
            "Unable to load the PA micro component manifest."
        ) from exc


def _validate_micro_component_artifact(
    manifest: ComponentArtifactManifest,
    manifest_path: Path,
) -> ComponentArtifactValidationResult:
    try:
        return validate_component_artifact_from_manifest(manifest, manifest_path)
    except (ArtifactValidationError, ComponentManifestError) as exc:
        raise MicroArtifactValidationError(
            "Unable to validate the local PA micro component artifact."
        ) from exc


def _resolve_validated_artifact_directory(
    manifest_path: Path,
    artifact_directory: str,
) -> Path:
    try:
        manifest_directory = manifest_path.resolve(strict=True).parent
        resolved_artifact_directory = (
            manifest_directory / artifact_directory
        ).resolve(strict=True)
        resolved_artifact_directory.relative_to(manifest_directory)
    except FileNotFoundError as exc:
        raise MicroArtifactValidationError(
            "The validated PA micro artifact directory is not available locally."
        ) from exc
    except OSError as exc:
        raise MicroArtifactValidationError(
            "Unable to resolve the validated PA micro artifact directory."
        ) from exc
    except ValueError as exc:
        raise MicroArtifactValidationError(
            "The validated PA micro artifact directory must remain inside the manifest directory."
        ) from exc

    return resolved_artifact_directory


def _validate_selected_production_identity(
    base_runtime: LoadedModelRuntime,
    micro_manifest: ComponentArtifactManifest,
    micro_validation: ComponentArtifactValidationResult,
) -> None:
    pa_constants = _load_pa_identity_constants()
    base_manifest = base_runtime.manifest
    validation_scope = micro_validation.validation_scope
    ensemble = micro_validation.ensemble

    _require_equal(base_manifest.track, _EXPECTED_TRACK, "Base manifest track")
    _require_equal(micro_manifest.track, _EXPECTED_TRACK, "Micro manifest track")
    _require_equal(micro_validation.track, _EXPECTED_TRACK, "Micro validation track")
    _require_equal(base_manifest.source_run, _EXPECTED_BASE_SOURCE_RUN, "Base source run")
    _require_equal(base_manifest.model_version, _EXPECTED_BASE_SOURCE_RUN, "Base model version")
    _require_equal(micro_manifest.source_run, _EXPECTED_MICRO_SOURCE_RUN, "Micro source run")
    _require_equal(micro_manifest.model_version, _EXPECTED_MICRO_SOURCE_RUN, "Micro model version")
    _require_equal(micro_validation.source_run, _EXPECTED_MICRO_SOURCE_RUN, "Validated micro source run")
    _require_equal(base_manifest.model_sha256, _EXPECTED_BASE_MODEL_SHA256, "Base model SHA256")
    _require_equal(micro_manifest.model_sha256, _EXPECTED_MICRO_MODEL_SHA256, "Micro model SHA256")
    _require_equal(micro_validation.model_sha256, _EXPECTED_MICRO_MODEL_SHA256, "Validated micro model SHA256")
    _require_equal(micro_manifest.artifact_role, _EXPECTED_ARTIFACT_ROLE, "Micro artifact role")
    _require_equal(micro_validation.artifact_role, _EXPECTED_ARTIFACT_ROLE, "Validated micro artifact role")
    _require_equal(ensemble.board_submission_id, _EXPECTED_BOARD_SUBMISSION_ID, "Board submission ID")
    _require_equal(ensemble.submission_file, _EXPECTED_SUBMISSION_FILE, "Submission file")
    _require_equal(ensemble.paired_base_run, _EXPECTED_BASE_SOURCE_RUN, "Paired base source run")
    _require_equal(validation_scope.board_validation_scope, "ensemble-only", "Board validation scope")
    _require_equal(validation_scope.artifact_integrity, "validated", "Artifact integrity scope")
    _require_equal(
        validation_scope.compatibility_metadata,
        "validated",
        "Compatibility metadata scope",
    )
    _require_equal(
        validation_scope.standalone_component_score_asserted,
        False,
        "Standalone component score assertion",
    )
    _require_equal(base_manifest.architecture, _EXPECTED_ARCHITECTURE, "Base architecture")
    _require_equal(micro_manifest.architecture, _EXPECTED_ARCHITECTURE, "Micro architecture")
    _require_equal(base_manifest.tokenizer_class, _EXPECTED_TOKENIZER_CLASS, "Base tokenizer class")
    _require_equal(micro_manifest.tokenizer_class, _EXPECTED_TOKENIZER_CLASS, "Micro tokenizer class")
    _require_equal(base_manifest.number_of_labels, _EXPECTED_LABEL_COUNT, "Base label count")
    _require_equal(micro_manifest.number_of_labels, _EXPECTED_LABEL_COUNT, "Micro label count")
    _require_equal(base_manifest.vocabulary_size, _EXPECTED_VOCABULARY_SIZE, "Base vocabulary size")
    _require_equal(
        micro_manifest.vocabulary_size,
        _EXPECTED_VOCABULARY_SIZE,
        "Micro vocabulary size",
    )

    _require_equal(base_runtime.device, _SUPPORTED_DEVICE, "Base runtime device")
    _require_equal(base_manifest.inference.max_length, pa_constants["max_length"], "Base max length")
    _require_equal(base_manifest.inference.stride, pa_constants["stride"], "Base stride")
    _require_close(ensemble.base_weight, pa_constants["base_weight"], "Base ensemble weight")
    _require_close(ensemble.micro_weight, pa_constants["micro_weight"], "Micro ensemble weight")
    _require_equal(ensemble.max_length, pa_constants["max_length"], "Ensemble max length")
    _require_equal(ensemble.stride, pa_constants["stride"], "Ensemble stride")
    _require_close(
        ensemble.default_threshold,
        pa_constants["default_threshold"],
        "Default threshold",
    )
    _require_close(
        ensemble.punctuation_threshold,
        pa_constants["punctuation_threshold"],
        "Punctuation threshold",
    )


def _load_pa_identity_constants() -> dict[str, float | int]:
    from wathiq_araseg.pa.postprocessing import DEFAULT_THRESHOLD, PUNCTUATION_THRESHOLD
    from wathiq_araseg.pa.window_inference import (
        PA_BASE_WEIGHT,
        PA_MAX_LENGTH,
        PA_MICRO_WEIGHT,
        PA_STRIDE,
    )

    return {
        "base_weight": PA_BASE_WEIGHT,
        "micro_weight": PA_MICRO_WEIGHT,
        "max_length": PA_MAX_LENGTH,
        "stride": PA_STRIDE,
        "default_threshold": DEFAULT_THRESHOLD,
        "punctuation_threshold": PUNCTUATION_THRESHOLD,
    }


def _load_validated_micro_model(
    artifact_directory: Path,
    device: str,
) -> Any:
    auto_model_for_token_classification = _import_micro_model_loader()

    try:
        model = auto_model_for_token_classification.from_pretrained(
            str(artifact_directory),
            local_files_only=True,
            trust_remote_code=False,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise MicroModelLoadError(
            "Unable to load the validated local PA micro model artifact."
        ) from exc

    try:
        model = model.to(device)
        model.eval()
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise MicroModelLoadError(
            "Unable to prepare the validated local PA micro model on the requested device."
        ) from exc

    return model


def _import_micro_model_loader() -> Any:
    try:
        transformers_module = importlib.import_module("transformers")
    except ImportError as exc:
        raise MicroModelLoadError(
            "Transformers runtime dependencies are not installed for the PA micro model."
        ) from exc

    return transformers_module.AutoModelForTokenClassification


def _validate_runtime_compatibility(
    base_runtime: LoadedModelRuntime,
    micro_manifest: ComponentArtifactManifest,
    micro_validation: ComponentArtifactValidationResult,
    micro_model: Any,
) -> None:
    base_manifest = base_runtime.manifest
    shared_tokenizer = base_runtime.tokenizer
    base_model = base_runtime.model

    tokenizer_vocabulary_size = _get_tokenizer_vocabulary_size(shared_tokenizer)
    if tokenizer_vocabulary_size != base_manifest.vocabulary_size:
        raise RuntimeCompatibilityMismatchError(
            "The shared base tokenizer vocabulary size does not match the validated base manifest."
        )
    if tokenizer_vocabulary_size != micro_manifest.vocabulary_size:
        raise RuntimeCompatibilityMismatchError(
            "The shared base tokenizer vocabulary size does not match the validated micro manifest."
        )

    if not _is_tokenizer_class_compatible(shared_tokenizer, base_manifest.tokenizer_class):
        raise RuntimeCompatibilityMismatchError(
            "The shared base tokenizer class is incompatible with the validated base manifest."
        )
    if not _is_tokenizer_class_compatible(shared_tokenizer, micro_manifest.tokenizer_class):
        raise RuntimeCompatibilityMismatchError(
            "The shared base tokenizer class is incompatible with the validated micro manifest."
        )

    _validate_loaded_model_metadata(
        model=base_model,
        manifest_architecture=base_manifest.architecture,
        manifest_label_count=base_manifest.number_of_labels,
        expected_vocabulary_size=tokenizer_vocabulary_size,
        stage_name="base",
    )
    _validate_loaded_model_metadata(
        model=micro_model,
        manifest_architecture=micro_manifest.architecture,
        manifest_label_count=micro_manifest.number_of_labels,
        expected_vocabulary_size=tokenizer_vocabulary_size,
        stage_name="micro",
    )

    _require_equal(
        micro_validation.model_version,
        micro_manifest.model_version,
        "Validated micro model version",
    )
    _require_equal(
        micro_validation.source_run,
        micro_manifest.source_run,
        "Validated micro source run",
    )


def _validate_loaded_model_metadata(
    *,
    model: Any,
    manifest_architecture: str,
    manifest_label_count: int,
    expected_vocabulary_size: int,
    stage_name: str,
) -> None:
    config = getattr(model, "config", None)
    loaded_architecture = _extract_loaded_model_architecture(model)
    if loaded_architecture != manifest_architecture:
        raise RuntimeCompatibilityMismatchError(
            f"The loaded {stage_name} model architecture is incompatible with the validated manifest."
        )

    num_labels = getattr(config, "num_labels", None)
    if num_labels != manifest_label_count:
        raise RuntimeCompatibilityMismatchError(
            f"The loaded {stage_name} model label count is incompatible with the validated manifest."
        )

    vocabulary_size = getattr(config, "vocab_size", None)
    if vocabulary_size != expected_vocabulary_size:
        raise RuntimeCompatibilityMismatchError(
            f"The loaded {stage_name} model vocabulary size is incompatible with the shared tokenizer."
        )

    if getattr(model, "training", None) is not False:
        raise RuntimeCompatibilityMismatchError(
            f"The loaded {stage_name} model must remain in evaluation mode."
        )


def _extract_loaded_model_architecture(model: Any) -> str:
    architectures = getattr(getattr(model, "config", None), "architectures", None)
    if isinstance(architectures, list) and architectures:
        first_architecture = architectures[0]
        if isinstance(first_architecture, str) and first_architecture.strip():
            return first_architecture

    return model.__class__.__name__


def _get_tokenizer_vocabulary_size(tokenizer: Any) -> int:
    try:
        vocabulary_size = len(tokenizer)
    except (AttributeError, TypeError, ValueError) as exc:
        raise RuntimeCompatibilityMismatchError(
            "The shared base tokenizer must expose a stable vocabulary size."
        ) from exc

    if isinstance(vocabulary_size, bool) or not isinstance(vocabulary_size, int):
        raise RuntimeCompatibilityMismatchError(
            "The shared base tokenizer must expose an integer vocabulary size."
        )

    return vocabulary_size


def _is_tokenizer_class_compatible(tokenizer: Any, manifest_tokenizer_class: str) -> bool:
    loaded_class_name = tokenizer.__class__.__name__
    if loaded_class_name == manifest_tokenizer_class:
        return True
    return loaded_class_name == f"{manifest_tokenizer_class}Fast"


def _build_inference_engine(
    *,
    tokenizer: Any,
    base_model: Any,
    micro_model: Any,
) -> Any:
    from wathiq_araseg.pa.exceptions import TokenizerModelCompatibilityError
    from wathiq_araseg.pa.window_inference import PAEnsembleWindowInferenceEngine

    try:
        return PAEnsembleWindowInferenceEngine(tokenizer, base_model, micro_model)
    except TokenizerModelCompatibilityError as exc:
        raise RuntimeCompatibilityMismatchError(
            "The shared tokenizer and loaded PA models are not mutually compatible."
        ) from exc
    except Exception as exc:
        raise PAEngineConstructionError(
            "Unable to construct the PA ensemble inference engine."
        ) from exc


def _build_pipeline(inference_engine: Any) -> PAPipeline:
    from wathiq_araseg.pa.pipeline import PAPipeline

    try:
        return PAPipeline(inference_engine)
    except Exception as exc:
        raise PAPipelineConstructionError(
            "Unable to construct the production-local PAPipeline."
        ) from exc


def _require_equal(actual: Any, expected: Any, field_name: str) -> None:
    if actual != expected:
        raise ProductionIdentityMismatchError(
            f"{field_name} does not match the selected PA production identity."
        )


def _require_close(actual: float, expected: float, field_name: str) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=_WEIGHT_TOLERANCE):
        raise ProductionIdentityMismatchError(
            f"{field_name} does not match the selected PA production identity."
        )
