from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
import warnings

from fastapi.testclient import TestClient
from pydantic.warnings import UnsupportedFieldAttributeWarning

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.app import create_app  # noqa: E402
from wathiq_araseg.config import ServiceConfig  # noqa: E402
from wathiq_araseg.segmentation import SegmentationRequest, SentenceSegmentationService  # noqa: E402


class SegmentationEndpointTests(unittest.TestCase):
    def test_valid_pa_request_returns_200_and_exact_contract_fields(self) -> None:
        text = "سطر أول\r\nسطر ثان"

        with TestClient(create_app(_build_config())) as client:
            response = client.post(
                "/api/v1/segment",
                json={
                    "documentId": "document-123",
                    "text": text,
                    "track": "PA",
                    "preserveParagraphs": True,
                    "returnConfidence": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(
            set(payload.keys()),
            {
                "documentId",
                "status",
                "provider",
                "track",
                "modelVersion",
                "modelSha256",
                "sourceTextHash",
                "tokenCount",
                "boundaryCount",
                "processingTimeMs",
                "segmentedText",
                "sentences",
            },
        )
        self.assertEqual(payload["documentId"], "document-123")
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["provider"], "AraSeg")
        self.assertEqual(payload["track"], "PA")
        self.assertEqual(payload["modelVersion"], "fake-pa-contract-v1")
        self.assertIn("fake", payload["modelSha256"])
        self.assertEqual(
            payload["sourceTextHash"],
            hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(payload["tokenCount"], 1)
        self.assertEqual(payload["boundaryCount"], 1)
        self.assertIsInstance(payload["processingTimeMs"], int)
        self.assertGreaterEqual(payload["processingTimeMs"], 0)
        self.assertEqual(payload["segmentedText"], "سطر أول\nسطر ثان")
        self.assertEqual(len(payload["sentences"]), 1)
        self.assertEqual(
            set(payload["sentences"][0].keys()),
            {
                "index",
                "text",
                "startToken",
                "endToken",
                "confidence",
                "paragraphIndex",
            },
        )
        self.assertEqual(payload["sentences"][0]["index"], 0)
        self.assertEqual(payload["sentences"][0]["text"], "سطر أول\nسطر ثان")
        self.assertEqual(payload["sentences"][0]["startToken"], 0)
        self.assertEqual(payload["sentences"][0]["endToken"], 0)
        self.assertEqual(payload["sentences"][0]["confidence"], 0.0)
        self.assertEqual(payload["sentences"][0]["paragraphIndex"], 0)

    def test_return_confidence_false_returns_null_confidence(self) -> None:
        with TestClient(create_app(_build_config())) as client:
            response = client.post(
                "/api/v1/segment",
                json={
                    "documentId": "document-456",
                    "text": "نص كامل",
                    "track": "PA",
                    "preserveParagraphs": True,
                    "returnConfidence": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["sentences"][0]["confidence"])

    def test_blank_document_identifier_returns_structured_invalid_input(self) -> None:
        payload = self._post_json(
            {
                "documentId": "   ",
                "text": "نص صالح",
                "track": "PA",
                "preserveParagraphs": True,
                "returnConfidence": True,
            }
        )

        self.assertEqual(payload["status_code"], 400)
        self.assertEqual(payload["body"]["error"]["code"], "INVALID_INPUT")
        self.assertTrue(payload["body"]["error"]["requestId"])

    def test_blank_text_returns_structured_invalid_input(self) -> None:
        payload = self._post_json(
            {
                "documentId": "doc-001",
                "text": " \t ",
                "track": "PA",
                "preserveParagraphs": True,
                "returnConfidence": True,
            }
        )

        self.assertEqual(payload["status_code"], 400)
        self.assertEqual(payload["body"]["error"]["code"], "INVALID_INPUT")
        self.assertTrue(payload["body"]["error"]["requestId"])

    def test_snake_case_request_returns_structured_invalid_input(self) -> None:
        payload = self._post_json(
            {
                "document_id": "doc-snake",
                "text": "Ù†Øµ ØµØ§Ù„Ø­",
                "track": "PA",
                "preserve_paragraphs": True,
                "return_confidence": True,
            }
        )

        self.assertEqual(payload["status_code"], 400)
        self.assertEqual(payload["body"]["error"]["code"], "INVALID_INPUT")
        self.assertTrue(payload["body"]["error"]["requestId"])

    def test_mixed_request_names_return_structured_invalid_input(self) -> None:
        payload = self._post_json(
            {
                "documentId": "doc-mixed",
                "text": "Ù†Øµ ØµØ§Ù„Ø­",
                "track": "PA",
                "preserveParagraphs": True,
                "return_confidence": True,
            }
        )

        self.assertEqual(payload["status_code"], 400)
        self.assertEqual(payload["body"]["error"]["code"], "INVALID_INPUT")
        self.assertTrue(payload["body"]["error"]["requestId"])

    def test_unsupported_track_returns_structured_error(self) -> None:
        payload = self._post_json(
            {
                "documentId": "doc-002",
                "text": "نص صالح",
                "track": "NP",
                "preserveParagraphs": True,
                "returnConfidence": True,
            }
        )

        self.assertEqual(payload["status_code"], 422)
        self.assertEqual(payload["body"]["error"]["code"], "UNSUPPORTED_TRACK")
        self.assertTrue(payload["body"]["error"]["requestId"])

    def test_preserve_paragraphs_false_returns_invalid_options_error(self) -> None:
        payload = self._post_json(
            {
                "documentId": "doc-003",
                "text": "نص صالح",
                "track": "PA",
                "preserveParagraphs": False,
                "returnConfidence": True,
            }
        )

        self.assertEqual(payload["status_code"], 422)
        self.assertEqual(
            payload["body"]["error"]["code"],
            "INVALID_SEGMENTATION_OPTIONS",
        )
        self.assertTrue(payload["body"]["error"]["requestId"])

    def test_malformed_request_returns_structured_invalid_input(self) -> None:
        with TestClient(create_app(_build_config())) as client:
            response = client.post(
                "/api/v1/segment",
                content="{",
                headers={"Content-Type": "application/json"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_INPUT")
        self.assertTrue(response.json()["error"]["requestId"])

    def test_valid_request_emits_no_unsupported_field_attribute_warning(self) -> None:
        response, captured_warnings = self._post_json_with_warning_capture(
            {
                "documentId": "doc-warning-free",
                "text": "Ù†Øµ ØµØ§Ù„Ø­",
                "track": "PA",
                "preserveParagraphs": True,
                "returnConfidence": True,
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_warnings, [])

    def test_valid_request_succeeds_when_unsupported_field_warning_is_error(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error", UnsupportedFieldAttributeWarning)

            with TestClient(create_app(_build_config())) as client:
                response = client.post(
                    "/api/v1/segment",
                    json={
                        "documentId": "doc-warning-error",
                        "text": "Ù†Øµ ØµØ§Ù„Ø­",
                        "track": "PA",
                        "preserveParagraphs": True,
                        "returnConfidence": True,
                    },
                )

        self.assertEqual(response.status_code, 200)

    def test_route_delegates_through_sentence_segmentation_service(self) -> None:
        app = create_app(_build_config())

        with mock.patch.object(
            app.state.segmentation_service,
            "segment",
            wraps=app.state.segmentation_service.segment,
        ) as segment_mock:
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/segment",
                    json={
                        "documentId": "doc-004",
                        "text": "نص صالح",
                        "track": "PA",
                        "preserveParagraphs": True,
                        "returnConfidence": True,
                    },
                )

        self.assertEqual(response.status_code, 200)
        segment_mock.assert_called_once()
        domain_request = segment_mock.call_args.args[0]
        self.assertIsInstance(domain_request, SegmentationRequest)
        self.assertEqual(domain_request.document_id, "doc-004")
        self.assertEqual(domain_request.text, "نص صالح")
        self.assertEqual(domain_request.track, "PA")

    def test_route_does_not_instantiate_fake_pipeline(self) -> None:
        app = create_app(_build_config())

        with mock.patch(
            "wathiq_araseg.segmentation.fake_pipeline.FakeSegmentationPipeline",
            side_effect=AssertionError("Route must not instantiate FakeSegmentationPipeline."),
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/segment",
                    json={
                        "documentId": "doc-005",
                        "text": "نص صالح",
                        "track": "PA",
                        "preserveParagraphs": True,
                        "returnConfidence": True,
                    },
                )

        self.assertEqual(response.status_code, 200)

    def test_real_model_loader_is_not_called(self) -> None:
        app = create_app(_build_config())

        with mock.patch(
            "wathiq_araseg.runtime.model_loader.load_local_model_runtime",
            side_effect=AssertionError("Real model loader must not be called."),
        ) as load_model_mock:
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/segment",
                    json={
                        "documentId": "doc-006",
                        "text": "نص صالح",
                        "track": "PA",
                        "preserveParagraphs": True,
                        "returnConfidence": True,
                    },
                )

        self.assertEqual(response.status_code, 200)
        load_model_mock.assert_not_called()

    def test_health_remains_unchanged(self) -> None:
        with TestClient(create_app(_build_config())) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "healthy",
                "service": "wathiq-araseg-service",
                "version": "0.1.0",
                "modelReady": False,
                "device": "cpu",
            },
        )

    def test_models_endpoint_does_not_exist(self) -> None:
        with TestClient(create_app(_build_config())) as client:
            response = client.get("/api/v1/models")

        self.assertEqual(response.status_code, 404)

    def test_route_inventory_contains_only_framework_health_and_segment_routes(self) -> None:
        app = create_app(_build_config())

        route_paths = sorted(route.path for route in app.routes)

        self.assertEqual(
            route_paths,
            [
                "/api/v1/segment",
                "/docs",
                "/docs/oauth2-redirect",
                "/health",
                "/openapi.json",
                "/redoc",
            ],
        )

    def test_openapi_contains_segmentation_endpoint_and_documented_schemas(self) -> None:
        with TestClient(create_app(_build_config())) as client:
            response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("/health", payload["paths"])
        self.assertIn("/api/v1/segment", payload["paths"])
        segment_operation = payload["paths"]["/api/v1/segment"]["post"]
        self.assertIn("400", segment_operation["responses"])
        self.assertIn("422", segment_operation["responses"])

        request_schema_name = (
            segment_operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
            .split("/")[-1]
        )
        request_properties = payload["components"]["schemas"][request_schema_name]["properties"]
        self.assertEqual(
            set(request_properties.keys()),
            {"documentId", "text", "track", "preserveParagraphs", "returnConfidence"},
        )

        response_schema_name = (
            segment_operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
            .split("/")[-1]
        )
        response_properties = payload["components"]["schemas"][response_schema_name]["properties"]
        self.assertEqual(
            set(response_properties.keys()),
            {
                "documentId",
                "status",
                "provider",
                "track",
                "modelVersion",
                "modelSha256",
                "sourceTextHash",
                "tokenCount",
                "boundaryCount",
                "processingTimeMs",
                "segmentedText",
                "sentences",
            },
        )

        sentence_schema_name = (
            response_properties["sentences"]["items"]["$ref"].split("/")[-1]
        )
        sentence_properties = payload["components"]["schemas"][sentence_schema_name]["properties"]
        self.assertEqual(
            set(sentence_properties.keys()),
            {"index", "text", "startToken", "endToken", "confidence", "paragraphIndex"},
        )
        self.assertIn("examples", segment_operation["requestBody"]["content"]["application/json"])
        self.assertIn("example", segment_operation["responses"]["200"]["content"]["application/json"])

    def _post_json(self, body: dict[str, object]) -> dict[str, object]:
        with TestClient(create_app(_build_config())) as client:
            response = client.post("/api/v1/segment", json=body)

        return {"status_code": response.status_code, "body": response.json()}

    def _post_json_with_warning_capture(
        self,
        body: dict[str, object],
    ) -> tuple[object, list[str]]:
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", UnsupportedFieldAttributeWarning)

            with TestClient(create_app(_build_config())) as client:
                response = client.post("/api/v1/segment", json=body)

        unsupported_warnings = [
            str(warning.message)
            for warning in caught_warnings
            if issubclass(warning.category, UnsupportedFieldAttributeWarning)
        ]

        return response, unsupported_warnings


def _build_config() -> ServiceConfig:
    return ServiceConfig(
        service_name="wathiq-araseg-service",
        service_version="0.1.0",
        environment="test",
        host="127.0.0.1",
        port=8000,
        log_level="INFO",
        inference_device="cpu",
    )


if __name__ == "__main__":
    unittest.main()
