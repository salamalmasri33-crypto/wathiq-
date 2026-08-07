from __future__ import annotations

import hashlib
import importlib
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
    ComponentManifestNotFoundError,
    ComponentManifestParseError,
    ComponentManifestValidationError,
    InvalidArtifactRoleError,
    InvalidEnsembleMetadataError,
    InvalidValidationScopeError,
    UnsupportedComponentManifestSchemaError,
    load_component_manifest,
)
from wathiq_araseg.artifacts.manifest import ManifestValidationError, load_manifest  # noqa: E402


def _sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _build_component_manifest_dict() -> dict:
    config_bytes = json.dumps(
        {
            "architectures": ["BertForTokenClassification"],
            "num_labels": 2,
            "vocab_size": 30001,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    model_bytes = b"component-model"
    tokenizer_json_bytes = b'{"tokenizer":true}'
    tokenizer_config_bytes = json.dumps(
        {"tokenizer_class": "BertTokenizer"},
        separators=(",", ":"),
    ).encode("utf-8")
    training_args_bytes = b"training-args"

    return {
        "schemaVersion": "1.0",
        "provider": "AraSeg",
        "track": "PA",
        "artifactRole": "micro-ensemble-member",
        "modelVersion": "PA_micro_20260724_174832",
        "sourceRun": "PA_micro_20260724_174832",
        "artifactDirectory": "best_model",
        "modelFile": "model.safetensors",
        "modelSha256": _sha256_hex(model_bytes),
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
            "config.json": {
                "sizeBytes": len(config_bytes),
                "sha256": _sha256_hex(config_bytes),
            },
            "model.safetensors": {
                "sizeBytes": len(model_bytes),
                "sha256": _sha256_hex(model_bytes),
            },
            "tokenizer.json": {
                "sizeBytes": len(tokenizer_json_bytes),
                "sha256": _sha256_hex(tokenizer_json_bytes),
            },
            "tokenizer_config.json": {
                "sizeBytes": len(tokenizer_config_bytes),
                "sha256": _sha256_hex(tokenizer_config_bytes),
            },
            "training_args.bin": {
                "sizeBytes": len(training_args_bytes),
                "sha256": _sha256_hex(training_args_bytes),
            },
        },
    }


class LoadComponentManifestTests(unittest.TestCase):
    def test_load_component_manifest_parses_valid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(_build_component_manifest_dict(), indent=2),
                encoding="utf-8",
            )

            manifest = load_component_manifest(manifest_path)

        self.assertEqual(manifest.track, "PA")
        self.assertEqual(manifest.artifact_role, "micro-ensemble-member")
        self.assertEqual(manifest.ensemble.board_submission_id, 861752)
        self.assertFalse(manifest.validation_scope.standalone_component_score_asserted)
        self.assertIn("model.safetensors", manifest.files)

    def test_load_component_manifest_raises_for_missing_file(self) -> None:
        with self.assertRaises(ComponentManifestNotFoundError):
            load_component_manifest(Path("missing-component-manifest.json"))

    def test_load_component_manifest_raises_for_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text("{", encoding="utf-8")

            with self.assertRaises(ComponentManifestParseError):
                load_component_manifest(manifest_path)

    def test_load_component_manifest_rejects_missing_required_top_level_fields(self) -> None:
        required_fields = (
            "schemaVersion",
            "provider",
            "track",
            "artifactRole",
            "modelVersion",
            "sourceRun",
            "artifactDirectory",
            "modelFile",
            "modelSha256",
            "architecture",
            "tokenizerClass",
            "numberOfLabels",
            "vocabularySize",
            "validationScope",
            "ensemble",
            "files",
        )

        for field_name in required_fields:
            with self.subTest(field_name=field_name):
                manifest_data = _build_component_manifest_dict()
                del manifest_data[field_name]

                with tempfile.TemporaryDirectory() as temp_dir:
                    manifest_path = Path(temp_dir) / "manifest.json"
                    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

                    with self.assertRaises(ComponentManifestValidationError):
                        load_component_manifest(manifest_path)

    def test_load_component_manifest_allows_unknown_fields_to_match_standard_parser_behavior(self) -> None:
        manifest_data = _build_component_manifest_dict()
        manifest_data["unknownField"] = "ignored"

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

            manifest = load_component_manifest(manifest_path)

        self.assertEqual(manifest.track, "PA")

    def test_load_component_manifest_rejects_invalid_controlled_identity_fields(self) -> None:
        invalid_cases = (
            ("schemaVersion", "2.0", UnsupportedComponentManifestSchemaError),
            ("track", "SA", ComponentManifestValidationError),
            ("artifactRole", "micro-model", InvalidArtifactRoleError),
        )

        for field_name, invalid_value, expected_error in invalid_cases:
            with self.subTest(field_name=field_name):
                manifest_data = _build_component_manifest_dict()
                manifest_data[field_name] = invalid_value

                with tempfile.TemporaryDirectory() as temp_dir:
                    manifest_path = Path(temp_dir) / "manifest.json"
                    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

                    with self.assertRaises(expected_error):
                        load_component_manifest(manifest_path)

    def test_load_component_manifest_rejects_invalid_validation_scope(self) -> None:
        invalid_cases = (
            ("artifactIntegrity", "pending"),
            ("compatibilityMetadata", "pending"),
            ("boardValidationScope", "standalone"),
            ("standaloneComponentScoreAsserted", True),
        )

        for field_name, invalid_value in invalid_cases:
            with self.subTest(field_name=field_name):
                manifest_data = _build_component_manifest_dict()
                manifest_data["validationScope"][field_name] = invalid_value

                with tempfile.TemporaryDirectory() as temp_dir:
                    manifest_path = Path(temp_dir) / "manifest.json"
                    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

                    with self.assertRaises(InvalidValidationScopeError):
                        load_component_manifest(manifest_path)

    def test_load_component_manifest_rejects_invalid_ensemble_metadata(self) -> None:
        invalid_cases = (
            ("baseWeight", -0.1),
            ("baseWeight", True),
            ("microWeight", 1.2),
            ("microWeight", 0.10),
            ("defaultThreshold", 1.1),
            ("punctuationThreshold", -0.1),
            ("maxLength", 0),
            ("stride", 0),
            ("boardSubmissionId", 0),
            ("pairedBaseRun", ""),
            ("submissionFile", ""),
        )

        for field_name, invalid_value in invalid_cases:
            with self.subTest(field_name=field_name):
                manifest_data = _build_component_manifest_dict()
                manifest_data["ensemble"][field_name] = invalid_value
                if field_name == "microWeight" and invalid_value == 0.10:
                    manifest_data["ensemble"]["baseWeight"] = 0.95

                with tempfile.TemporaryDirectory() as temp_dir:
                    manifest_path = Path(temp_dir) / "manifest.json"
                    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

                    with self.assertRaises(InvalidEnsembleMetadataError):
                        load_component_manifest(manifest_path)

    def test_load_component_manifest_rejects_unsafe_paths(self) -> None:
        invalid_cases = (
            ("artifactDirectory", "C:/outside/best_model"),
            ("artifactDirectory", "../outside"),
            ("modelFile", "C:/outside/model.safetensors"),
            ("modelFile", "../model.safetensors"),
        )

        for field_name, invalid_value in invalid_cases:
            with self.subTest(field_name=field_name):
                manifest_data = _build_component_manifest_dict()
                manifest_data[field_name] = invalid_value
                if field_name == "modelFile":
                    manifest_data["modelSha256"] = manifest_data["files"]["model.safetensors"]["sha256"]

                with tempfile.TemporaryDirectory() as temp_dir:
                    manifest_path = Path(temp_dir) / "manifest.json"
                    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

                    with self.assertRaises(ComponentManifestValidationError):
                        load_component_manifest(manifest_path)

    def test_load_component_manifest_rejects_unsafe_file_inventory_entries(self) -> None:
        invalid_keys = ("../config.json", "C:/outside/config.json")

        for invalid_key in invalid_keys:
            with self.subTest(invalid_key=invalid_key):
                manifest_data = _build_component_manifest_dict()
                manifest_data["files"][invalid_key] = manifest_data["files"].pop("config.json")

                with tempfile.TemporaryDirectory() as temp_dir:
                    manifest_path = Path(temp_dir) / "manifest.json"
                    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

                    with self.assertRaises(ComponentManifestValidationError):
                        load_component_manifest(manifest_path)

    def test_load_component_manifest_rejects_invalid_file_inventory(self) -> None:
        invalid_mutations = (
            ("empty-files", lambda data: data.__setitem__("files", {})),
            (
                "negative-size",
                lambda data: data["files"]["config.json"].__setitem__("sizeBytes", -1),
            ),
            (
                "bool-size",
                lambda data: data["files"]["config.json"].__setitem__("sizeBytes", True),
            ),
            (
                "bad-sha",
                lambda data: data["files"]["config.json"].__setitem__("sha256", "bad"),
            ),
            ("missing-model-entry", lambda data: data["files"].pop("model.safetensors")),
            ("model-sha-mismatch", lambda data: data.__setitem__("modelSha256", "0" * 64)),
        )

        for case_name, mutate in invalid_mutations:
            with self.subTest(case_name=case_name):
                manifest_data = _build_component_manifest_dict()
                mutate(manifest_data)

                with tempfile.TemporaryDirectory() as temp_dir:
                    manifest_path = Path(temp_dir) / "manifest.json"
                    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

                    with self.assertRaises(ComponentManifestValidationError):
                        load_component_manifest(manifest_path)

    def test_load_component_manifest_rejects_duplicate_file_entries(self) -> None:
        raw_manifest = """
{
  "schemaVersion": "1.0",
  "provider": "AraSeg",
  "track": "PA",
  "artifactRole": "micro-ensemble-member",
  "modelVersion": "PA_micro_20260724_174832",
  "sourceRun": "PA_micro_20260724_174832",
  "artifactDirectory": "best_model",
  "modelFile": "model.safetensors",
  "modelSha256": "1111111111111111111111111111111111111111111111111111111111111111",
  "architecture": "BertForTokenClassification",
  "tokenizerClass": "BertTokenizer",
  "numberOfLabels": 2,
  "vocabularySize": 30001,
  "validationScope": {
    "artifactIntegrity": "validated",
    "compatibilityMetadata": "validated",
    "boardValidationScope": "ensemble-only",
    "standaloneComponentScoreAsserted": false
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
    "punctuationThreshold": 0.31
  },
  "files": {
    "model.safetensors": {
      "sizeBytes": 1,
      "sha256": "1111111111111111111111111111111111111111111111111111111111111111"
    },
    "model.safetensors": {
      "sizeBytes": 1,
      "sha256": "1111111111111111111111111111111111111111111111111111111111111111"
    }
  }
}
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(raw_manifest, encoding="utf-8")

            with self.assertRaises(ComponentManifestValidationError):
                load_component_manifest(manifest_path)

    def test_standard_manifest_loader_remains_standard_only(self) -> None:
        with self.assertRaises(ManifestValidationError):
            load_manifest(SERVICE_ROOT / "models" / "pa" / "micro" / "manifest.json")

    def test_real_micro_component_manifest_matches_expected_configuration(self) -> None:
        manifest_path = SERVICE_ROOT / "models" / "pa" / "micro" / "manifest.json"
        manifest = load_component_manifest(manifest_path)

        self.assertEqual(manifest.schema_version, "1.0")
        self.assertEqual(manifest.provider, "AraSeg")
        self.assertEqual(manifest.track, "PA")
        self.assertEqual(manifest.artifact_role, "micro-ensemble-member")
        self.assertEqual(manifest.model_version, "PA_micro_20260724_174832")
        self.assertEqual(manifest.source_run, "PA_micro_20260724_174832")
        self.assertEqual(manifest.artifact_directory, "best_model")
        self.assertEqual(manifest.model_file, "model.safetensors")
        self.assertEqual(
            manifest.model_sha256,
            "af194bf0b31823febd1f9479f771fe29409751561f56205dec03358ab38eb9f3",
        )
        self.assertEqual(manifest.ensemble.board_submission_id, 861752)
        self.assertEqual(manifest.ensemble.base_weight, 0.95)
        self.assertEqual(manifest.ensemble.micro_weight, 0.05)
        self.assertEqual(manifest.ensemble.max_length, 512)
        self.assertEqual(manifest.ensemble.stride, 64)
        self.assertEqual(manifest.ensemble.default_threshold, 0.543)
        self.assertEqual(manifest.ensemble.punctuation_threshold, 0.31)
        self.assertEqual(manifest.validation_scope.board_validation_scope, "ensemble-only")
        self.assertFalse(manifest.validation_scope.standalone_component_score_asserted)

    def test_importing_artifacts_package_has_no_runtime_side_effects(self) -> None:
        module_names = [
            "wathiq_araseg.artifacts",
            "wathiq_araseg.artifacts.manifest",
            "wathiq_araseg.artifacts.validator",
        ]
        saved_modules = {
            name: sys.modules.get(name)
            for name in module_names
        }
        for name in module_names:
            sys.modules.pop(name, None)

        had_torch = "torch" in sys.modules
        had_transformers = "transformers" in sys.modules

        try:
            with mock.patch.object(
                Path,
                "read_text",
                autospec=True,
                side_effect=AssertionError("artifact import must not read files"),
            ), mock.patch.object(
                Path,
                "open",
                autospec=True,
                side_effect=AssertionError("artifact import must not open files"),
            ):
                module = importlib.import_module("wathiq_araseg.artifacts")
        finally:
            for name, saved_module in saved_modules.items():
                if saved_module is not None:
                    sys.modules[name] = saved_module

        self.assertTrue(hasattr(module, "load_component_manifest"))
        self.assertEqual("torch" in sys.modules, had_torch)
        self.assertEqual("transformers" in sys.modules, had_transformers)


if __name__ == "__main__":
    unittest.main()
