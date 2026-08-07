from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

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
    ArtifactValidationError,
    validate_artifact_manifest,
)
from wathiq_araseg.artifacts.checksum import (  # noqa: E402
    ChecksumFileAccessError,
    compute_sha256,
)


def _sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _build_artifact_fixture(
    root_path: Path,
    *,
    artifact_directory: str = "best_model",
    model_sha256: str | None = None,
) -> tuple[Path, dict[str, bytes]]:
    artifact_root = root_path / "best_model"
    artifact_root.mkdir(parents=True, exist_ok=True)

    file_bytes = {
        "config.json": b'{"labels": 2}',
        "model.safetensors": b"temporary-model-binary",
    }

    for file_name, content in file_bytes.items():
        (artifact_root / file_name).write_bytes(content)

    model_file_sha = _sha256_hex(file_bytes["model.safetensors"])
    manifest = {
        "schemaVersion": "1.0",
        "provider": "AraSeg",
        "track": "PA",
        "modelVersion": "fixture-model",
        "sourceRun": "fixture-run",
        "artifactDirectory": artifact_directory,
        "modelFile": "model.safetensors",
        "modelSha256": model_sha256 or model_file_sha,
        "architecture": "BertForTokenClassification",
        "tokenizerClass": "BertTokenizer",
        "numberOfLabels": 2,
        "vocabularySize": 30001,
        "inference": {
            "maxLength": 512,
            "stride": 64,
            "defaultThreshold": 0.567,
            "endPunctuationThreshold": 0.32,
            "paragraphRuleEnabled": True,
            "forceLastEnabled": True,
        },
        "validatedBlindResult": {
            "precision": 0.934,
            "recall": 0.939,
            "f1": 0.934,
            "submissionId": 861529,
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


class ArtifactValidatorTests(unittest.TestCase):
    def test_compute_sha256_wraps_permission_error_while_opening(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "artifact.bin"
            file_path.write_bytes(b"data")

            with mock.patch.object(
                Path,
                "open",
                autospec=True,
                side_effect=PermissionError("denied"),
            ):
                with self.assertRaises(ChecksumFileAccessError) as context:
                    compute_sha256(file_path)

        self.assertIsInstance(context.exception.__cause__, PermissionError)

    def test_compute_sha256_wraps_os_error_while_reading(self) -> None:
        class FailingReader:
            def __enter__(self) -> FailingReader:
                return self

            def __exit__(self, exc_type, exc, exc_tb) -> bool:
                return False

            def read(self, _chunk_size: int) -> bytes:
                raise OSError("read failure")

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "artifact.bin"
            file_path.write_bytes(b"data")

            with mock.patch.object(
                Path,
                "open",
                autospec=True,
                return_value=FailingReader(),
            ):
                with self.assertRaises(ChecksumFileAccessError) as context:
                    compute_sha256(file_path)

        self.assertIsInstance(context.exception.__cause__, OSError)

    def test_validate_artifact_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_artifact_fixture(Path(temp_dir))
            (Path(temp_dir) / "best_model" / "config.json").unlink()

            with self.assertRaises(ArtifactFileMissingError):
                validate_artifact_manifest(manifest_path)

    def test_validate_artifact_rejects_incorrect_file_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_artifact_fixture(Path(temp_dir))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["config.json"]["sizeBytes"] += 1
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            with self.assertRaises(ArtifactFileSizeMismatchError):
                validate_artifact_manifest(manifest_path)

    def test_validate_artifact_rejects_incorrect_file_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_artifact_fixture(Path(temp_dir))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["config.json"]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            with self.assertRaises(ArtifactChecksumMismatchError):
                validate_artifact_manifest(manifest_path)

    def test_validate_artifact_rejects_absolute_artifact_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_artifact_fixture(
                Path(temp_dir),
                artifact_directory="C:/external/best_model",
            )

            with self.assertRaises(ArtifactPathSafetyError):
                validate_artifact_manifest(manifest_path)

    def test_validate_artifact_rejects_parent_directory_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_artifact_fixture(
                Path(temp_dir),
                artifact_directory="../outside",
            )

            with self.assertRaises(ArtifactPathSafetyError):
                validate_artifact_manifest(manifest_path)

    def test_validate_artifact_rejects_model_sha256_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_artifact_fixture(
                Path(temp_dir),
                model_sha256="1" * 64,
            )

            with self.assertRaises(ArtifactInventoryError):
                validate_artifact_manifest(manifest_path)

    def test_validate_artifact_wraps_os_error_from_metadata_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, _ = _build_artifact_fixture(Path(temp_dir))
            target_path = (Path(temp_dir) / "best_model" / "config.json").resolve()
            original_stat = Path.stat

            def failing_stat(self: Path, *args, **kwargs):
                if self == target_path:
                    raise OSError("metadata failure")
                return original_stat(self, *args, **kwargs)

            with mock.patch.object(Path, "stat", autospec=True, side_effect=failing_stat):
                with self.assertRaises(ArtifactValidationError) as context:
                    validate_artifact_manifest(manifest_path)

        self.assertIsInstance(context.exception.__cause__, OSError)

    def test_validate_artifact_succeeds_for_complete_temporary_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path, file_bytes = _build_artifact_fixture(Path(temp_dir))

            result = validate_artifact_manifest(manifest_path)

        self.assertEqual(result.track, "PA")
        self.assertEqual(result.model_version, "fixture-model")
        self.assertEqual(result.artifact_directory, "best_model")
        self.assertEqual(result.model_file, "model.safetensors")
        self.assertEqual(result.model_sha256, _sha256_hex(file_bytes["model.safetensors"]))
        self.assertEqual(result.validated_file_count, 2)
        self.assertEqual(result.validated_files, ("config.json", "model.safetensors"))

    def test_real_pa_artifact_validation_or_skip(self) -> None:
        manifest_path = SERVICE_ROOT / "models" / "pa" / "manifest.json"
        artifact_root = SERVICE_ROOT / "models" / "pa" / "best_model"

        if not artifact_root.is_dir():
            self.skipTest("Real PA best_model directory is not present locally.")

        result = validate_artifact_manifest(manifest_path)

        self.assertEqual(
            result.model_sha256,
            "7d76a8a15a302800b2ba4dfafb3815f50a03370a5b12c7d6734491ac68bfb9d1",
        )


if __name__ == "__main__":
    unittest.main()
