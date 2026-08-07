from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.artifacts import (  # noqa: E402
    ArtifactChecksumMismatchError,
    ArtifactFileMissingError,
    ArtifactFileSizeMismatchError,
    ArtifactInventoryError,
    ArtifactPathSafetyError,
    ComponentArtifactManifest,
    ComponentManifestValidationError,
    ComponentCompatibilityMismatchError,
    ComponentValidationScope,
    ComponentEnsembleMetadata,
    ManifestFileEntry,
    load_component_manifest,
    validate_component_artifact_from_manifest,
    validate_component_artifact_manifest,
    validate_artifact_manifest,
)


def _sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _build_component_artifact_fixture(
    root_path: Path,
    *,
    artifact_directory: str = "best_model",
    model_sha256: str | None = None,
) -> tuple[Path, dict[str, bytes]]:
    artifact_root = root_path / "best_model"
    artifact_root.mkdir(parents=True, exist_ok=True)

    file_bytes = {
        "config.json": json.dumps(
            {
                "architectures": ["BertForTokenClassification"],
                "num_labels": 2,
                "vocab_size": 30001,
            },
            separators=(",", ":"),
        ).encode("utf-8"),
        "model.safetensors": b"temporary-component-model",
        "tokenizer.json": b'{"tokenizer":true}',
        "tokenizer_config.json": json.dumps(
            {"tokenizer_class": "BertTokenizer"},
            separators=(",", ":"),
        ).encode("utf-8"),
        "training_args.bin": b"training-args",
    }

    for file_name, content in file_bytes.items():
        (artifact_root / file_name).write_bytes(content)

    manifest = {
        "schemaVersion": "1.0",
        "provider": "AraSeg",
        "track": "PA",
        "artifactRole": "micro-ensemble-member",
        "modelVersion": "PA_micro_20260724_174832",
        "sourceRun": "PA_micro_20260724_174832",
        "artifactDirectory": artifact_directory,
        "modelFile": "model.safetensors",
        "modelSha256": model_sha256 or _sha256_hex(file_bytes["model.safetensors"]),
        "architecture": "BertForTokenClassification",
        "tokenizerClass": "BertTokenizer",
        "numberOfLabels": 2,
        "vocabularySize": 30001,
        "validationScope": {
            "artifactIntegrity": "validated",
            "compatibilityMetadata": "validated",
            "boardValidationScope": "ensemble-only",
            "standaloneComponentScoreAsserted": False,
        },
        "ensemble": {
            "boardSubmissionId": 861752,
            "submissionFile": "pa_current_micro_ens_a095_m005_d0543_e0310.zip",
            "pairedBaseRun": "PA_finetune_20260723_104427",
            "baseWeight": 0.95,
            "microWeight": 0.05,
            "maxLength": 512,
            "stride": 64,
            "defaultThreshold": 0.543,
            "punctuationThreshold": 0.31,
        },
        "files": {
            file_name: {
                "sizeBytes": len(content),
                "sha256": _sha256_hex(content),
            }
            for file_name, content in file_bytes.items()
        },
    }

    manifest_path = root_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path, file_bytes


def _build_component_manifest_object(
    *,
    artifact_directory: str = "best_model",
    files: dict[str, ManifestFileEntry] | None = None,
) -> ComponentArtifactManifest:
    manifest_files = files or {
        "config.json": ManifestFileEntry(size_bytes=1, sha256="1" * 64),
        "model.safetensors": ManifestFileEntry(size_bytes=1, sha256="2" * 64),
        "tokenizer.json": ManifestFileEntry(size_bytes=1, sha256="3" * 64),
        "tokenizer_config.json": ManifestFileEntry(size_bytes=1, sha256="4" * 64),
        "training_args.bin": ManifestFileEntry(size_bytes=1, sha256="5" * 64),
    }

    return ComponentArtifactManifest(
        schema_version="1.0",
        provider="AraSeg",
        track="PA",
        artifact_role="micro-ensemble-member",
        model_version="PA_micro_20260724_174832",
        source_run="PA_micro_20260724_174832",
        artifact_directory=artifact_directory,
        model_file="model.safetensors",
        model_sha256=manifest_files["model.safetensors"].sha256,
        architecture="BertForTokenClassification",
        tokenizer_class="BertTokenizer",
        number_of_labels=2,
        vocabulary_size=30001,
        validation_scope=ComponentValidationScope(
            artifact_integrity="validated",
            compatibility_metadata="validated",
            board_validation_scope="ensemble-only",
            standalone_component_score_asserted=False,
        ),
        ensemble=ComponentEnsembleMetadata(
            board_submission_id=861752,
            submission_file="pa_current_micro_ens_a095_m005_d0543_e0310.zip",
            paired_base_run="PA_finetune_20260723_104427",
            base_weight=0.95,
            micro_weight=0.05,
            max_length=512,
            stride=64,
            default_threshold=0.543,
            punctuation_threshold=0.31,
        ),
        files=manifest_files,
    )


class ComponentArtifactValidatorTests(unittest.TestCase):
    def test_validate_component_artifact_succeeds_for_complete_temporary_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, file_bytes = _build_component_artifact_fixture(Path(temp_dir))

            result = validate_component_artifact_manifest(manifest_path)

        self.assertEqual(result.track, "PA")
        self.assertEqual(result.artifact_role, "micro-ensemble-member")
        self.assertEqual(result.model_version, "PA_micro_20260724_174832")
        self.assertEqual(result.source_run, "PA_micro_20260724_174832")
        self.assertEqual(result.artifact_directory, "best_model")
        self.assertEqual(result.model_file, "model.safetensors")
        self.assertEqual(result.model_sha256, _sha256_hex(file_bytes["model.safetensors"]))
        self.assertEqual(result.ensemble.board_submission_id, 861752)
        self.assertEqual(result.validated_file_count, 5)

    def test_validate_component_artifact_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_component_artifact_fixture(Path(temp_dir))
            (Path(temp_dir) / "best_model" / "config.json").unlink()

            with self.assertRaises(ArtifactFileMissingError):
                validate_component_artifact_manifest(manifest_path)

    def test_validate_component_artifact_rejects_incorrect_file_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_component_artifact_fixture(Path(temp_dir))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["config.json"]["sizeBytes"] += 1
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            with self.assertRaises(ArtifactFileSizeMismatchError):
                validate_component_artifact_manifest(manifest_path)

    def test_validate_component_artifact_rejects_incorrect_file_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_component_artifact_fixture(Path(temp_dir))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["config.json"]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            with self.assertRaises(ArtifactChecksumMismatchError):
                validate_component_artifact_manifest(manifest_path)

    def test_validate_component_artifact_rejects_model_file_missing_from_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_component_artifact_fixture(Path(temp_dir))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["modelFile"] = "missing-model.safetensors"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            with self.assertRaises(ComponentManifestValidationError):
                load_component_manifest(manifest_path)

    def test_validate_component_artifact_rejects_unsafe_resolution(self) -> None:
        manifest = _build_component_manifest_object(artifact_directory="../outside")

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text("{}", encoding="utf-8")

            with self.assertRaises(ArtifactPathSafetyError):
                validate_component_artifact_from_manifest(manifest, manifest_path)

    def test_validate_component_artifact_rejects_architecture_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_component_artifact_fixture(Path(temp_dir))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["architecture"] = "RobertaForTokenClassification"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            with self.assertRaises(ComponentCompatibilityMismatchError):
                validate_component_artifact_manifest(manifest_path)

    def test_validate_component_artifact_rejects_label_count_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_component_artifact_fixture(Path(temp_dir))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["numberOfLabels"] = 3
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            with self.assertRaises(ComponentCompatibilityMismatchError):
                validate_component_artifact_manifest(manifest_path)

    def test_validate_component_artifact_rejects_vocabulary_size_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_component_artifact_fixture(Path(temp_dir))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["vocabularySize"] = 30002
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            with self.assertRaises(ComponentCompatibilityMismatchError):
                validate_component_artifact_manifest(manifest_path)

    def test_validate_component_artifact_rejects_tokenizer_class_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_component_artifact_fixture(Path(temp_dir))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["tokenizerClass"] = "RobertaTokenizer"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            with self.assertRaises(ComponentCompatibilityMismatchError):
                validate_component_artifact_manifest(manifest_path)

    def test_standard_base_manifest_validation_remains_unchanged(self) -> None:
        manifest_path = SERVICE_ROOT / "models" / "pa" / "manifest.json"
        artifact_root = SERVICE_ROOT / "models" / "pa" / "best_model"

        if not artifact_root.is_dir():
            self.skipTest("Real PA best_model directory is not present locally.")

        result = validate_artifact_manifest(manifest_path)
        self.assertEqual(result.track, "PA")
        self.assertEqual(result.model_file, "model.safetensors")

    def test_real_micro_component_artifact_validation_or_skip(self) -> None:
        manifest_path = SERVICE_ROOT / "models" / "pa" / "micro" / "manifest.json"
        artifact_root = SERVICE_ROOT / "models" / "pa" / "micro" / "best_model"

        if not artifact_root.is_dir():
            self.skipTest("Real micro best_model directory is not present locally.")

        start_time = time.perf_counter()
        result = validate_component_artifact_manifest(manifest_path)
        duration_seconds = time.perf_counter() - start_time

        self.assertEqual(result.track, "PA")
        self.assertEqual(result.artifact_role, "micro-ensemble-member")
        self.assertEqual(result.source_run, "PA_micro_20260724_174832")
        self.assertEqual(result.ensemble.board_submission_id, 861752)
        self.assertEqual(result.ensemble.micro_weight, 0.05)
        self.assertFalse(result.validation_scope.standalone_component_score_asserted)
        self.assertEqual(
            result.model_sha256,
            "af194bf0b31823febd1f9479f771fe29409751561f56205dec03358ab38eb9f3",
        )
        self.assertEqual(result.validated_file_count, 5)
        self.assertGreater(duration_seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
