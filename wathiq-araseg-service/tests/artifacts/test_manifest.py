from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.artifacts.manifest import (  # noqa: E402
    ManifestNotFoundError,
    ManifestParseError,
    ManifestValidationError,
    load_manifest,
)


def _sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _build_manifest_dict() -> dict:
    model_bytes = b"fake-model"
    config_bytes = b'{"test": true}'

    return {
        "schemaVersion": "1.0",
        "provider": "AraSeg",
        "track": "PA",
        "modelVersion": "test-model",
        "sourceRun": "test-run",
        "artifactDirectory": "best_model",
        "modelFile": "model.safetensors",
        "modelSha256": _sha256_hex(model_bytes),
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
            "config.json": {
                "sizeBytes": len(config_bytes),
                "sha256": _sha256_hex(config_bytes),
            },
            "model.safetensors": {
                "sizeBytes": len(model_bytes),
                "sha256": _sha256_hex(model_bytes),
            },
        },
    }


class LoadManifestTests(unittest.TestCase):
    def test_load_manifest_parses_valid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(_build_manifest_dict(), indent=2),
                encoding="utf-8",
            )

            manifest = load_manifest(manifest_path)

        self.assertEqual(manifest.track, "PA")
        self.assertEqual(manifest.model_version, "test-model")
        self.assertEqual(manifest.inference.max_length, 512)
        self.assertEqual(manifest.validated_blind_result.submission_id, 861529)
        self.assertIn("model.safetensors", manifest.files)

    def test_load_manifest_raises_for_missing_file(self) -> None:
        missing_path = Path("missing-manifest.json")

        with self.assertRaises(ManifestNotFoundError):
            load_manifest(missing_path)

    def test_load_manifest_raises_for_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text("{", encoding="utf-8")

            with self.assertRaises(ManifestParseError):
                load_manifest(manifest_path)

    def test_load_manifest_raises_for_missing_required_field(self) -> None:
        manifest_data = _build_manifest_dict()
        del manifest_data["modelVersion"]

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_load_manifest_raises_for_invalid_sha256_format(self) -> None:
        manifest_data = _build_manifest_dict()
        manifest_data["files"]["model.safetensors"]["sha256"] = "invalid-sha"

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

            with self.assertRaises(ManifestValidationError):
                load_manifest(manifest_path)

    def test_real_pa_manifest_matches_expected_configuration(self) -> None:
        manifest_path = SERVICE_ROOT / "models" / "pa" / "manifest.json"
        manifest = load_manifest(manifest_path)

        self.assertEqual(manifest.schema_version, "1.0")
        self.assertEqual(manifest.provider, "AraSeg")
        self.assertEqual(manifest.track, "PA")
        self.assertEqual(manifest.model_version, "PA_finetune_20260723_104427")
        self.assertEqual(manifest.source_run, "PA_finetune_20260723_104427")
        self.assertEqual(manifest.artifact_directory, "best_model")
        self.assertEqual(manifest.model_file, "model.safetensors")
        self.assertEqual(
            manifest.model_sha256,
            "7d76a8a15a302800b2ba4dfafb3815f50a03370a5b12c7d6734491ac68bfb9d1",
        )
        self.assertEqual(manifest.inference.max_length, 512)
        self.assertEqual(manifest.inference.stride, 64)
        self.assertEqual(manifest.inference.default_threshold, 0.567)
        self.assertEqual(manifest.inference.end_punctuation_threshold, 0.32)
        self.assertTrue(manifest.inference.paragraph_rule_enabled)
        self.assertTrue(manifest.inference.force_last_enabled)
        self.assertEqual(manifest.validated_blind_result.precision, 0.934)
        self.assertEqual(manifest.validated_blind_result.recall, 0.939)
        self.assertEqual(manifest.validated_blind_result.f1, 0.934)
        self.assertEqual(manifest.validated_blind_result.submission_id, 861529)


if __name__ == "__main__":
    unittest.main()
