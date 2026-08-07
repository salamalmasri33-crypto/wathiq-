"""Local integrity validation for AraSeg artifact manifests and files."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .checksum import ChecksumError, ChecksumFileNotFoundError, compute_sha256
from .manifest import (
    ArtifactManifest,
    ComponentArtifactManifest,
    ComponentEnsembleMetadata,
    ComponentValidationScope,
    load_component_manifest,
    load_manifest,
    _require_safe_relative_path_syntax,
)


class ArtifactValidationError(Exception):
    """Base exception for artifact integrity validation failures."""


class ArtifactPathSafetyError(ArtifactValidationError):
    """Raised when manifest paths are absolute or escape the manifest directory."""


class ArtifactInventoryError(ArtifactValidationError):
    """Raised when the manifest inventory is internally inconsistent."""


class ArtifactFileMissingError(ArtifactValidationError):
    """Raised when an expected artifact file is absent."""


class ArtifactFileSizeMismatchError(ArtifactValidationError):
    """Raised when an artifact file size does not match the manifest."""


class ArtifactChecksumMismatchError(ArtifactValidationError):
    """Raised when an artifact file checksum does not match the manifest."""


class ComponentCompatibilityMismatchError(ArtifactValidationError):
    """Raised when local component metadata conflicts with the component manifest."""


@dataclass(frozen=True, slots=True)
class ArtifactValidationResult:
    """Structured success result for a validated local artifact."""

    track: str
    model_version: str
    artifact_directory: str
    model_file: str
    model_sha256: str
    validated_files: tuple[str, ...]

    @property
    def validated_file_count(self) -> int:
        return len(self.validated_files)


@dataclass(frozen=True, slots=True)
class ComponentArtifactValidationResult:
    """Structured success result for a validated local component artifact."""

    track: str
    artifact_role: str
    model_version: str
    source_run: str
    artifact_directory: str
    model_file: str
    model_sha256: str
    validation_scope: ComponentValidationScope
    ensemble: ComponentEnsembleMetadata
    validated_files: tuple[str, ...]

    @property
    def validated_file_count(self) -> int:
        return len(self.validated_files)


def validate_artifact_manifest(manifest_path: Path) -> ArtifactValidationResult:
    """Load a manifest from disk and validate its full local artifact inventory."""

    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)
    return validate_artifact_from_manifest(manifest, manifest_path)


def validate_component_artifact_manifest(manifest_path: Path) -> ComponentArtifactValidationResult:
    """Load a component manifest from disk and validate its local artifact inventory."""

    manifest_path = Path(manifest_path)
    manifest = load_component_manifest(manifest_path)
    return validate_component_artifact_from_manifest(manifest, manifest_path)


def validate_artifact_from_manifest(
    manifest: ArtifactManifest,
    manifest_path: Path,
) -> ArtifactValidationResult:
    """Validate a manifest model against its local artifact directory."""

    manifest_path = Path(manifest_path)
    manifest_dir = _resolve_manifest_directory(manifest_path)
    artifact_root = _resolve_manifest_child_directory(
        manifest_dir,
        manifest.artifact_directory,
        "artifactDirectory",
    )

    if manifest.model_file not in manifest.files:
        raise ArtifactInventoryError(
            "Manifest modelFile is not present in the files inventory."
        )

    model_inventory_entry = manifest.files[manifest.model_file]
    if manifest.model_sha256 != model_inventory_entry.sha256:
        raise ArtifactInventoryError(
            "Manifest modelSha256 does not match the files inventory entry for modelFile."
        )

    validated_files: list[str] = []
    for file_name, expected in manifest.files.items():
        artifact_path = _resolve_manifest_child_file(
            artifact_root,
            file_name,
            f"files['{file_name}']",
        )

        actual_size = _inspect_artifact_file_size(artifact_path, file_name)
        if actual_size != expected.size_bytes:
            raise ArtifactFileSizeMismatchError(
                f"Artifact file size mismatch for {file_name}: "
                f"expected {expected.size_bytes}, found {actual_size}."
            )

        actual_sha256 = _compute_artifact_sha256(artifact_path, file_name)
        if actual_sha256 != expected.sha256:
            raise ArtifactChecksumMismatchError(
                f"Artifact SHA256 mismatch for {file_name}: "
                f"expected {expected.sha256}, found {actual_sha256}."
            )

        validated_files.append(file_name)

    return ArtifactValidationResult(
        track=manifest.track,
        model_version=manifest.model_version,
        artifact_directory=manifest.artifact_directory,
        model_file=manifest.model_file,
        model_sha256=manifest.model_sha256,
        validated_files=tuple(sorted(validated_files)),
    )


def validate_component_artifact_from_manifest(
    manifest: ComponentArtifactManifest,
    manifest_path: Path,
) -> ComponentArtifactValidationResult:
    """Validate a component manifest model against its local artifact directory."""

    manifest_path = Path(manifest_path)
    manifest_dir = _resolve_manifest_directory(manifest_path)
    artifact_root = _resolve_manifest_child_directory(
        manifest_dir,
        manifest.artifact_directory,
        "artifactDirectory",
    )

    if manifest.model_file not in manifest.files:
        raise ArtifactInventoryError(
            "Component manifest modelFile is not present in the files inventory."
        )

    model_inventory_entry = manifest.files[manifest.model_file]
    if manifest.model_sha256 != model_inventory_entry.sha256:
        raise ArtifactInventoryError(
            "Component manifest modelSha256 does not match the files inventory entry for modelFile."
        )

    validated_files: list[str] = []
    for file_name, expected in manifest.files.items():
        artifact_path = _resolve_manifest_child_file(
            artifact_root,
            file_name,
            f"files['{file_name}']",
        )

        actual_size = _inspect_artifact_file_size(artifact_path, file_name)
        if actual_size != expected.size_bytes:
            raise ArtifactFileSizeMismatchError(
                f"Artifact file size mismatch for {file_name}: "
                f"expected {expected.size_bytes}, found {actual_size}."
            )

        actual_sha256 = _compute_artifact_sha256(artifact_path, file_name)
        if actual_sha256 != expected.sha256:
            raise ArtifactChecksumMismatchError(
                f"Artifact SHA256 mismatch for {file_name}: "
                f"expected {expected.sha256}, found {actual_sha256}."
            )

        validated_files.append(file_name)

    _validate_component_compatibility_metadata(manifest, artifact_root)

    return ComponentArtifactValidationResult(
        track=manifest.track,
        artifact_role=manifest.artifact_role,
        model_version=manifest.model_version,
        source_run=manifest.source_run,
        artifact_directory=manifest.artifact_directory,
        model_file=manifest.model_file,
        model_sha256=manifest.model_sha256,
        validation_scope=manifest.validation_scope,
        ensemble=manifest.ensemble,
        validated_files=tuple(sorted(validated_files)),
    )


def _resolve_manifest_directory(manifest_path: Path) -> Path:
    try:
        return manifest_path.resolve(strict=True).parent
    except FileNotFoundError as exc:
        raise ArtifactValidationError("Manifest path could not be resolved.") from exc
    except OSError as exc:
        raise ArtifactValidationError("Unable to inspect manifest path.") from exc


def _resolve_manifest_child_directory(
    base_directory: Path,
    raw_relative_path: str,
    field_name: str,
) -> Path:
    relative_path = _parse_safe_relative_path(raw_relative_path, field_name)
    resolved_directory = _resolve_within_base(base_directory, relative_path, field_name)

    if not _path_exists(resolved_directory, raw_relative_path):
        raise ArtifactFileMissingError(f"Artifact directory does not exist: {raw_relative_path}")

    if not _is_directory(resolved_directory, raw_relative_path):
        raise ArtifactValidationError(
            f"Artifact directory path is not a directory: {raw_relative_path}"
        )

    return resolved_directory


def _resolve_manifest_child_file(
    base_directory: Path,
    raw_relative_path: str,
    field_name: str,
) -> Path:
    relative_path = _parse_safe_relative_path(raw_relative_path, field_name)
    return _resolve_within_base(base_directory, relative_path, field_name)


def _parse_safe_relative_path(raw_relative_path: str, field_name: str) -> Path:
    try:
        return _require_safe_relative_path_syntax(
            raw_relative_path,
            field_name,
            ValueError,
        )
    except ValueError as exc:
        raise ArtifactPathSafetyError(str(exc)) from exc


def _resolve_within_base(base_directory: Path, relative_path: Path, field_name: str) -> Path:
    try:
        resolved_base = base_directory.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ArtifactValidationError("Manifest directory could not be resolved.") from exc
    except OSError as exc:
        raise ArtifactValidationError("Unable to inspect manifest directory.") from exc

    try:
        candidate = (resolved_base / relative_path).resolve(strict=False)
    except OSError as exc:
        raise ArtifactValidationError(
            f"Unable to resolve path for field '{field_name}'."
        ) from exc

    try:
        candidate.relative_to(resolved_base)
    except ValueError as exc:
        raise ArtifactPathSafetyError(
            f"Field '{field_name}' must resolve inside the manifest directory."
        ) from exc

    return candidate


def _path_exists(path: Path, display_name: str) -> bool:
    try:
        return path.exists()
    except OSError as exc:
        raise ArtifactValidationError(
            f"Unable to inspect artifact path metadata for {display_name}."
        ) from exc


def _is_directory(path: Path, display_name: str) -> bool:
    try:
        return path.is_dir()
    except OSError as exc:
        raise ArtifactValidationError(
            f"Unable to inspect artifact directory metadata for {display_name}."
        ) from exc


def _inspect_artifact_file_size(path: Path, file_name: str) -> int:
    try:
        stat_result = path.stat()
    except FileNotFoundError as exc:
        raise ArtifactFileMissingError(f"Artifact file is missing: {file_name}") from exc
    except OSError as exc:
        raise ArtifactValidationError(
            f"Unable to inspect artifact file metadata for {file_name}."
        ) from exc

    if not path.is_file():
        raise ArtifactValidationError(f"Artifact path is not a regular file: {file_name}")

    return stat_result.st_size


def _compute_artifact_sha256(path: Path, file_name: str) -> str:
    try:
        return compute_sha256(path)
    except ChecksumFileNotFoundError as exc:
        raise ArtifactFileMissingError(f"Artifact file is missing: {file_name}") from exc
    except ChecksumError as exc:
        raise ArtifactValidationError(
            f"Unable to read artifact file contents for {file_name}."
        ) from exc


def _validate_component_compatibility_metadata(
    manifest: ComponentArtifactManifest,
    artifact_root: Path,
) -> None:
    config_data = _load_artifact_json_mapping(artifact_root / "config.json", "config.json")
    tokenizer_config_data = _load_artifact_json_mapping(
        artifact_root / "tokenizer_config.json",
        "tokenizer_config.json",
    )

    actual_architecture = _extract_component_architecture(config_data)
    if actual_architecture != manifest.architecture:
        raise ComponentCompatibilityMismatchError(
            "Artifact config architecture does not match the component manifest."
        )

    actual_label_count = _extract_component_label_count(config_data)
    if actual_label_count != manifest.number_of_labels:
        raise ComponentCompatibilityMismatchError(
            "Artifact config label count does not match the component manifest."
        )

    actual_vocabulary_size = _extract_positive_int(
        config_data.get("vocab_size"),
        "config.json.vocab_size",
    )
    if actual_vocabulary_size != manifest.vocabulary_size:
        raise ComponentCompatibilityMismatchError(
            "Artifact config vocabulary size does not match the component manifest."
        )

    actual_tokenizer_class = tokenizer_config_data.get("tokenizer_class")
    if not isinstance(actual_tokenizer_class, str) or not actual_tokenizer_class.strip():
        raise ComponentCompatibilityMismatchError(
            "Artifact tokenizer metadata must include a non-empty tokenizer_class."
        )
    if actual_tokenizer_class != manifest.tokenizer_class:
        raise ComponentCompatibilityMismatchError(
            "Artifact tokenizer class does not match the component manifest."
        )


def _load_artifact_json_mapping(path: Path, file_name: str) -> dict[str, object]:
    try:
        raw_content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ArtifactValidationError(
            f"Unable to read artifact metadata file contents for {file_name}."
        ) from exc

    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ComponentCompatibilityMismatchError(
            f"Artifact metadata JSON is malformed for {file_name}."
        ) from exc

    if not isinstance(data, dict):
        raise ComponentCompatibilityMismatchError(
            f"Artifact metadata for {file_name} must be a JSON object."
        )

    return data


def _extract_component_architecture(config_data: dict[str, object]) -> str:
    architectures = config_data.get("architectures")
    if not isinstance(architectures, list) or not architectures:
        raise ComponentCompatibilityMismatchError(
            "Artifact config must declare a non-empty architectures list."
        )

    architecture = architectures[0]
    if not isinstance(architecture, str) or not architecture.strip():
        raise ComponentCompatibilityMismatchError(
            "Artifact config architecture entry must be a non-empty string."
        )

    return architecture


def _extract_positive_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ComponentCompatibilityMismatchError(
            f"Artifact metadata field {field_name} must be an integer."
        )
    if value < 1:
        raise ComponentCompatibilityMismatchError(
            f"Artifact metadata field {field_name} must be >= 1."
        )
    return value


def _extract_component_label_count(config_data: dict[str, object]) -> int:
    num_labels = config_data.get("num_labels")
    if not isinstance(num_labels, bool) and isinstance(num_labels, int):
        if num_labels < 1:
            raise ComponentCompatibilityMismatchError(
                "Artifact config num_labels must be >= 1."
            )
        return num_labels

    id2label = config_data.get("id2label")
    label2id = config_data.get("label2id")

    id2label_count = _extract_mapping_count(id2label, "config.json.id2label")
    label2id_count = _extract_mapping_count(label2id, "config.json.label2id")

    if id2label_count and label2id_count and id2label_count != label2id_count:
        raise ComponentCompatibilityMismatchError(
            "Artifact config label mappings disagree on the label count."
        )

    if id2label_count:
        return id2label_count
    if label2id_count:
        return label2id_count

    raise ComponentCompatibilityMismatchError(
        "Artifact config must provide num_labels, id2label, or label2id metadata."
    )


def _extract_mapping_count(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not value:
        raise ComponentCompatibilityMismatchError(
            f"Artifact metadata field {field_name} must be a non-empty JSON object."
        )
    return len(value)
