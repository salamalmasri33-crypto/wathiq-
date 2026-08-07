"""Typed manifest parsing for local AraSeg production artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping
from pathlib import PurePosixPath
import math

_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_WINDOWS_ABSOLUTE_PATTERN = re.compile(r"^[A-Za-z]:/")
_SUPPORTED_COMPONENT_SCHEMA_VERSION = "1.0"
_SUPPORTED_COMPONENT_TRACK = "PA"
_SUPPORTED_COMPONENT_ARTIFACT_ROLE = "micro-ensemble-member"
_SUPPORTED_VALIDATION_STATE = "validated"
_SUPPORTED_BOARD_VALIDATION_SCOPE = "ensemble-only"
_WEIGHT_SUM_TOLERANCE = 1e-9


class ManifestError(Exception):
    """Base exception for manifest loading failures."""


class ManifestNotFoundError(ManifestError):
    """Raised when a manifest file path does not exist."""


class ManifestParseError(ManifestError):
    """Raised when manifest JSON cannot be parsed."""


class ManifestValidationError(ManifestError):
    """Raised when manifest content is missing required fields or types."""


class ComponentManifestError(ManifestError):
    """Base exception for component manifest loading failures."""


class ComponentManifestNotFoundError(ComponentManifestError):
    """Raised when a component manifest file path does not exist."""


class ComponentManifestParseError(ComponentManifestError):
    """Raised when component manifest JSON cannot be parsed."""


class ComponentManifestValidationError(ComponentManifestError):
    """Raised when component manifest content is missing required fields or types."""


class UnsupportedComponentManifestSchemaError(ComponentManifestValidationError):
    """Raised when a component manifest schema version is unsupported."""


class InvalidArtifactRoleError(ComponentManifestValidationError):
    """Raised when a component manifest declares an unsupported artifact role."""


class InvalidValidationScopeError(ComponentManifestValidationError):
    """Raised when component validation-scope metadata is unsupported."""


class InvalidEnsembleMetadataError(ComponentManifestValidationError):
    """Raised when component ensemble metadata is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class ManifestFileEntry:
    """Expected metadata for one artifact file."""

    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class InferenceConfig:
    """Typed inference settings stored in the manifest."""

    max_length: int
    stride: int
    default_threshold: float
    end_punctuation_threshold: float
    paragraph_rule_enabled: bool
    force_last_enabled: bool


@dataclass(frozen=True, slots=True)
class ValidatedBlindResult:
    """Typed validation metrics stored in the manifest."""

    precision: float
    recall: float
    f1: float
    submission_id: int


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    """Typed AraSeg production artifact manifest."""

    schema_version: str
    provider: str
    track: str
    model_version: str
    source_run: str
    artifact_directory: str
    model_file: str
    model_sha256: str
    architecture: str
    tokenizer_class: str
    number_of_labels: int
    vocabulary_size: int
    inference: InferenceConfig
    validated_blind_result: ValidatedBlindResult
    files: Mapping[str, ManifestFileEntry]


@dataclass(frozen=True, slots=True)
class ComponentValidationScope:
    """Machine-readable validation scope for an ensemble component artifact."""

    artifact_integrity: str
    compatibility_metadata: str
    board_validation_scope: str
    standalone_component_score_asserted: bool


@dataclass(frozen=True, slots=True)
class ComponentEnsembleMetadata:
    """Typed ensemble provenance for a validated component artifact."""

    board_submission_id: int
    submission_file: str
    paired_base_run: str
    base_weight: float
    micro_weight: float
    max_length: int
    stride: int
    default_threshold: float
    punctuation_threshold: float


@dataclass(frozen=True, slots=True)
class ComponentArtifactManifest:
    """Typed AraSeg production artifact manifest for an ensemble component."""

    schema_version: str
    provider: str
    track: str
    artifact_role: str
    model_version: str
    source_run: str
    artifact_directory: str
    model_file: str
    model_sha256: str
    architecture: str
    tokenizer_class: str
    number_of_labels: int
    vocabulary_size: int
    validation_scope: ComponentValidationScope
    ensemble: ComponentEnsembleMetadata
    files: Mapping[str, ManifestFileEntry]


def load_manifest(manifest_path: Path) -> ArtifactManifest:
    """Load and validate a UTF-8 JSON artifact manifest."""

    manifest_path = Path(manifest_path)
    if not manifest_path.is_file():
        raise ManifestNotFoundError(f"Manifest file does not exist: {manifest_path}")

    try:
        raw_content = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"Unable to read manifest file: {manifest_path}") from exc

    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ManifestParseError(
            f"Manifest JSON is malformed at line {exc.lineno}, column {exc.colno}."
        ) from exc

    return _parse_manifest_mapping(data)


def load_component_manifest(manifest_path: Path) -> ComponentArtifactManifest:
    """Load and validate a UTF-8 JSON component artifact manifest."""

    manifest_path = Path(manifest_path)
    if not manifest_path.is_file():
        raise ComponentManifestNotFoundError(
            f"Component manifest file does not exist: {manifest_path}"
        )

    try:
        raw_content = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ComponentManifestError(
            f"Unable to read component manifest file: {manifest_path}"
        ) from exc

    try:
        data = json.loads(raw_content, object_pairs_hook=_reject_duplicate_json_keys)
    except json.JSONDecodeError as exc:
        raise ComponentManifestParseError(
            "Component manifest JSON is malformed at "
            f"line {exc.lineno}, column {exc.colno}."
        ) from exc
    except _DuplicateJsonKeyError as exc:
        raise ComponentManifestValidationError(
            f"Component manifest contains a duplicate JSON key: {exc.key}"
        ) from exc

    return _parse_component_manifest_mapping(data)


def _parse_manifest_mapping(data: Any) -> ArtifactManifest:
    root = _require_mapping(data, "manifest")
    file_entries = _parse_file_entries(_require_mapping(root.get("files"), "files"))

    model_sha256 = _require_sha256(root.get("modelSha256"), "modelSha256")

    return ArtifactManifest(
        schema_version=_require_string(root.get("schemaVersion"), "schemaVersion"),
        provider=_require_string(root.get("provider"), "provider"),
        track=_require_string(root.get("track"), "track"),
        model_version=_require_string(root.get("modelVersion"), "modelVersion"),
        source_run=_require_string(root.get("sourceRun"), "sourceRun"),
        artifact_directory=_require_string(root.get("artifactDirectory"), "artifactDirectory"),
        model_file=_require_string(root.get("modelFile"), "modelFile"),
        model_sha256=model_sha256,
        architecture=_require_string(root.get("architecture"), "architecture"),
        tokenizer_class=_require_string(root.get("tokenizerClass"), "tokenizerClass"),
        number_of_labels=_require_int(root.get("numberOfLabels"), "numberOfLabels", minimum=1),
        vocabulary_size=_require_int(root.get("vocabularySize"), "vocabularySize", minimum=1),
        inference=_parse_inference(_require_mapping(root.get("inference"), "inference")),
        validated_blind_result=_parse_blind_result(
            _require_mapping(root.get("validatedBlindResult"), "validatedBlindResult")
        ),
        files=MappingProxyType(file_entries),
    )


def _parse_component_manifest_mapping(data: Any) -> ComponentArtifactManifest:
    root = _require_mapping_with_error(data, "component manifest", ComponentManifestValidationError)
    file_entries = _parse_component_file_entries(
        _require_mapping_with_error(root.get("files"), "files", ComponentManifestValidationError)
    )

    schema_version = _require_string_with_error(
        root.get("schemaVersion"),
        "schemaVersion",
        ComponentManifestValidationError,
    )
    if schema_version != _SUPPORTED_COMPONENT_SCHEMA_VERSION:
        raise UnsupportedComponentManifestSchemaError(
            "Component manifest schemaVersion must be "
            f"'{_SUPPORTED_COMPONENT_SCHEMA_VERSION}'."
        )

    track = _require_string_with_error(root.get("track"), "track", ComponentManifestValidationError)
    if track != _SUPPORTED_COMPONENT_TRACK:
        raise ComponentManifestValidationError("Component manifest track must be 'PA'.")

    artifact_role = _require_string_with_error(
        root.get("artifactRole"),
        "artifactRole",
        ComponentManifestValidationError,
    )
    if artifact_role != _SUPPORTED_COMPONENT_ARTIFACT_ROLE:
        raise InvalidArtifactRoleError(
            "Component manifest artifactRole must be "
            f"'{_SUPPORTED_COMPONENT_ARTIFACT_ROLE}'."
        )

    artifact_directory = _require_string_with_error(
        root.get("artifactDirectory"),
        "artifactDirectory",
        ComponentManifestValidationError,
    )
    _require_safe_relative_path_syntax(
        artifact_directory,
        "artifactDirectory",
        ComponentManifestValidationError,
    )

    model_file = _require_string_with_error(
        root.get("modelFile"),
        "modelFile",
        ComponentManifestValidationError,
    )
    _require_safe_relative_path_syntax(
        model_file,
        "modelFile",
        ComponentManifestValidationError,
    )

    model_sha256 = _require_sha256_with_error(
        root.get("modelSha256"),
        "modelSha256",
        ComponentManifestValidationError,
    )

    if model_file not in file_entries:
        raise ComponentManifestValidationError(
            "Component manifest modelFile is not present in the files inventory."
        )

    if model_sha256 != file_entries[model_file].sha256:
        raise ComponentManifestValidationError(
            "Component manifest modelSha256 does not match the files inventory entry "
            "for modelFile."
        )

    return ComponentArtifactManifest(
        schema_version=schema_version,
        provider=_require_string_with_error(
            root.get("provider"),
            "provider",
            ComponentManifestValidationError,
        ),
        track=track,
        artifact_role=artifact_role,
        model_version=_require_string_with_error(
            root.get("modelVersion"),
            "modelVersion",
            ComponentManifestValidationError,
        ),
        source_run=_require_string_with_error(
            root.get("sourceRun"),
            "sourceRun",
            ComponentManifestValidationError,
        ),
        artifact_directory=artifact_directory,
        model_file=model_file,
        model_sha256=model_sha256,
        architecture=_require_string_with_error(
            root.get("architecture"),
            "architecture",
            ComponentManifestValidationError,
        ),
        tokenizer_class=_require_string_with_error(
            root.get("tokenizerClass"),
            "tokenizerClass",
            ComponentManifestValidationError,
        ),
        number_of_labels=_require_int_with_error(
            root.get("numberOfLabels"),
            "numberOfLabels",
            minimum=1,
            error_type=ComponentManifestValidationError,
        ),
        vocabulary_size=_require_int_with_error(
            root.get("vocabularySize"),
            "vocabularySize",
            minimum=1,
            error_type=ComponentManifestValidationError,
        ),
        validation_scope=_parse_component_validation_scope(
            _require_mapping_with_error(
                root.get("validationScope"),
                "validationScope",
                ComponentManifestValidationError,
            )
        ),
        ensemble=_parse_component_ensemble(
            _require_mapping_with_error(
                root.get("ensemble"),
                "ensemble",
                ComponentManifestValidationError,
            )
        ),
        files=MappingProxyType(file_entries),
    )


def _parse_inference(data: Mapping[str, Any]) -> InferenceConfig:
    return InferenceConfig(
        max_length=_require_int(data.get("maxLength"), "inference.maxLength", minimum=1),
        stride=_require_int(data.get("stride"), "inference.stride", minimum=1),
        default_threshold=_require_probability(
            data.get("defaultThreshold"),
            "inference.defaultThreshold",
        ),
        end_punctuation_threshold=_require_probability(
            data.get("endPunctuationThreshold"),
            "inference.endPunctuationThreshold",
        ),
        paragraph_rule_enabled=_require_bool(
            data.get("paragraphRuleEnabled"),
            "inference.paragraphRuleEnabled",
        ),
        force_last_enabled=_require_bool(
            data.get("forceLastEnabled"),
            "inference.forceLastEnabled",
        ),
    )


def _parse_blind_result(data: Mapping[str, Any]) -> ValidatedBlindResult:
    return ValidatedBlindResult(
        precision=_require_probability(data.get("precision"), "validatedBlindResult.precision"),
        recall=_require_probability(data.get("recall"), "validatedBlindResult.recall"),
        f1=_require_probability(data.get("f1"), "validatedBlindResult.f1"),
        submission_id=_require_int(
            data.get("submissionId"),
            "validatedBlindResult.submissionId",
            minimum=1,
        ),
    )


def _parse_file_entries(data: Mapping[str, Any]) -> dict[str, ManifestFileEntry]:
    if not data:
        raise ManifestValidationError("Field 'files' must not be empty.")

    parsed_entries: dict[str, ManifestFileEntry] = {}
    for file_name, item in data.items():
        if not isinstance(file_name, str) or not file_name.strip():
            raise ManifestValidationError("Manifest file inventory keys must be non-empty strings.")

        field_prefix = f"files['{file_name}']"
        parsed_entries[file_name] = ManifestFileEntry(
            size_bytes=_require_int(
                _require_mapping(item, field_prefix).get("sizeBytes"),
                f"{field_prefix}.sizeBytes",
                minimum=0,
            ),
            sha256=_require_sha256(
                _require_mapping(item, field_prefix).get("sha256"),
                f"{field_prefix}.sha256",
            ),
        )

    return parsed_entries


def _parse_component_validation_scope(data: Mapping[str, Any]) -> ComponentValidationScope:
    try:
        artifact_integrity = _require_string_with_error(
            data.get("artifactIntegrity"),
            "validationScope.artifactIntegrity",
            ComponentManifestValidationError,
        )
        compatibility_metadata = _require_string_with_error(
            data.get("compatibilityMetadata"),
            "validationScope.compatibilityMetadata",
            ComponentManifestValidationError,
        )
        board_validation_scope = _require_string_with_error(
            data.get("boardValidationScope"),
            "validationScope.boardValidationScope",
            ComponentManifestValidationError,
        )
        standalone_component_score_asserted = _require_bool_with_error(
            data.get("standaloneComponentScoreAsserted"),
            "validationScope.standaloneComponentScoreAsserted",
            ComponentManifestValidationError,
        )
    except ComponentManifestValidationError as exc:
        raise InvalidValidationScopeError("Component manifest validationScope is invalid.") from exc

    if artifact_integrity != _SUPPORTED_VALIDATION_STATE:
        raise InvalidValidationScopeError(
            "validationScope.artifactIntegrity must be 'validated'."
        )
    if compatibility_metadata != _SUPPORTED_VALIDATION_STATE:
        raise InvalidValidationScopeError(
            "validationScope.compatibilityMetadata must be 'validated'."
        )
    if board_validation_scope != _SUPPORTED_BOARD_VALIDATION_SCOPE:
        raise InvalidValidationScopeError(
            "validationScope.boardValidationScope must be 'ensemble-only'."
        )
    if standalone_component_score_asserted:
        raise InvalidValidationScopeError(
            "validationScope.standaloneComponentScoreAsserted must be false."
        )

    return ComponentValidationScope(
        artifact_integrity=artifact_integrity,
        compatibility_metadata=compatibility_metadata,
        board_validation_scope=board_validation_scope,
        standalone_component_score_asserted=standalone_component_score_asserted,
    )


def _parse_component_ensemble(data: Mapping[str, Any]) -> ComponentEnsembleMetadata:
    try:
        base_weight = _require_probability_with_error(
            data.get("baseWeight"),
            "ensemble.baseWeight",
            ComponentManifestValidationError,
        )
        micro_weight = _require_probability_with_error(
            data.get("microWeight"),
            "ensemble.microWeight",
            ComponentManifestValidationError,
        )
        board_submission_id = _require_int_with_error(
            data.get("boardSubmissionId"),
            "ensemble.boardSubmissionId",
            minimum=1,
            error_type=ComponentManifestValidationError,
        )
        submission_file = _require_string_with_error(
            data.get("submissionFile"),
            "ensemble.submissionFile",
            ComponentManifestValidationError,
        )
        paired_base_run = _require_string_with_error(
            data.get("pairedBaseRun"),
            "ensemble.pairedBaseRun",
            ComponentManifestValidationError,
        )
        max_length = _require_int_with_error(
            data.get("maxLength"),
            "ensemble.maxLength",
            minimum=1,
            error_type=ComponentManifestValidationError,
        )
        stride = _require_int_with_error(
            data.get("stride"),
            "ensemble.stride",
            minimum=1,
            error_type=ComponentManifestValidationError,
        )
        default_threshold = _require_probability_with_error(
            data.get("defaultThreshold"),
            "ensemble.defaultThreshold",
            ComponentManifestValidationError,
        )
        punctuation_threshold = _require_probability_with_error(
            data.get("punctuationThreshold"),
            "ensemble.punctuationThreshold",
            ComponentManifestValidationError,
        )
    except ComponentManifestValidationError as exc:
        raise InvalidEnsembleMetadataError(
            "Component manifest ensemble metadata is invalid."
        ) from exc

    total_weight = base_weight + micro_weight
    if not math.isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=_WEIGHT_SUM_TOLERANCE):
        raise InvalidEnsembleMetadataError(
            "ensemble.baseWeight and ensemble.microWeight must sum to 1.0."
        )

    return ComponentEnsembleMetadata(
        board_submission_id=board_submission_id,
        submission_file=submission_file,
        paired_base_run=paired_base_run,
        base_weight=base_weight,
        micro_weight=micro_weight,
        max_length=max_length,
        stride=stride,
        default_threshold=default_threshold,
        punctuation_threshold=punctuation_threshold,
    )


def _parse_component_file_entries(data: Mapping[str, Any]) -> dict[str, ManifestFileEntry]:
    if not data:
        raise ComponentManifestValidationError("Field 'files' must not be empty.")

    parsed_entries: dict[str, ManifestFileEntry] = {}
    for file_name, item in data.items():
        if not isinstance(file_name, str) or not file_name.strip():
            raise ComponentManifestValidationError(
                "Component manifest file inventory keys must be non-empty strings."
            )

        _require_safe_relative_path_syntax(
            file_name,
            f"files['{file_name}']",
            ComponentManifestValidationError,
        )

        field_prefix = f"files['{file_name}']"
        parsed_entries[file_name] = ManifestFileEntry(
            size_bytes=_require_int_with_error(
                _require_mapping_with_error(item, field_prefix, ComponentManifestValidationError).get(
                    "sizeBytes"
                ),
                f"{field_prefix}.sizeBytes",
                minimum=0,
                error_type=ComponentManifestValidationError,
            ),
            sha256=_require_sha256_with_error(
                _require_mapping_with_error(item, field_prefix, ComponentManifestValidationError).get(
                    "sha256"
                ),
                f"{field_prefix}.sha256",
                ComponentManifestValidationError,
            ),
        )

    return parsed_entries


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ManifestValidationError(f"Field '{field_name}' must be a JSON object.")
    return value


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestValidationError(f"Field '{field_name}' must be a non-empty string.")
    return value


def _require_int(value: Any, field_name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestValidationError(f"Field '{field_name}' must be an integer.")
    if value < minimum:
        raise ManifestValidationError(f"Field '{field_name}' must be >= {minimum}.")
    return value


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ManifestValidationError(f"Field '{field_name}' must be a boolean.")
    return value


def _require_probability(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestValidationError(f"Field '{field_name}' must be a number.")

    numeric_value = float(value)
    if not 0.0 <= numeric_value <= 1.0:
        raise ManifestValidationError(f"Field '{field_name}' must be between 0.0 and 1.0.")
    return numeric_value


def _require_sha256(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise ManifestValidationError(
            f"Field '{field_name}' must be a 64-character hexadecimal SHA256 string."
        )
    return value.lower()


def _require_mapping_with_error(
    value: Any,
    field_name: str,
    error_type: type[Exception],
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise error_type(f"Field '{field_name}' must be a JSON object.")
    return value


def _require_string_with_error(
    value: Any,
    field_name: str,
    error_type: type[Exception],
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise error_type(f"Field '{field_name}' must be a non-empty string.")
    return value


def _require_int_with_error(
    value: Any,
    field_name: str,
    minimum: int,
    error_type: type[Exception],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise error_type(f"Field '{field_name}' must be an integer.")
    if value < minimum:
        raise error_type(f"Field '{field_name}' must be >= {minimum}.")
    return value


def _require_bool_with_error(
    value: Any,
    field_name: str,
    error_type: type[Exception],
) -> bool:
    if not isinstance(value, bool):
        raise error_type(f"Field '{field_name}' must be a boolean.")
    return value


def _require_probability_with_error(
    value: Any,
    field_name: str,
    error_type: type[Exception],
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise error_type(f"Field '{field_name}' must be a number.")

    numeric_value = float(value)
    if not 0.0 <= numeric_value <= 1.0:
        raise error_type(f"Field '{field_name}' must be between 0.0 and 1.0.")
    return numeric_value


def _require_sha256_with_error(
    value: Any,
    field_name: str,
    error_type: type[Exception],
) -> str:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise error_type(
            f"Field '{field_name}' must be a 64-character hexadecimal SHA256 string."
        )
    return value.lower()


class _DuplicateJsonKeyError(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError(key)
        result[key] = value
    return result


def _require_safe_relative_path_syntax(
    raw_relative_path: str,
    field_name: str,
    error_type: type[Exception],
) -> Path:
    if not isinstance(raw_relative_path, str) or not raw_relative_path.strip():
        raise error_type(f"Field '{field_name}' must be a non-empty relative path.")

    normalized_path = raw_relative_path.replace("\\", "/")
    pure_path = PurePosixPath(normalized_path)

    if pure_path.is_absolute() or normalized_path.startswith("/") or _WINDOWS_ABSOLUTE_PATTERN.match(
        normalized_path
    ):
        raise error_type(f"Field '{field_name}' must not be an absolute path.")

    if any(part == ".." for part in pure_path.parts):
        raise error_type(f"Field '{field_name}' must not escape the manifest directory.")

    safe_parts = [part for part in pure_path.parts if part not in ("", ".")]
    return Path(*safe_parts) if safe_parts else Path(".")
