from __future__ import annotations

from pathlib import Path
import sys
import time
import unittest
from unittest import mock

from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg import app as app_module  # noqa: E402
from wathiq_araseg.app import ApplicationStartupError, create_app  # noqa: E402
from wathiq_araseg.config import ConfigurationError, ServiceConfig, load_service_config  # noqa: E402
from wathiq_araseg.runtime import BaseRuntimeLoadError  # noqa: E402
from wathiq_araseg.segmentation import (  # noqa: E402
    AbstractSegmentationPipeline,
    InvalidSegmentationInputError,
    InvalidSegmentationResultError,
    SegmentationRequest,
    SegmentationToken,
)


class InternalTokenizedConfigurationTests(unittest.TestCase):
    def test_internal_endpoint_defaults_to_disabled_without_manifest_paths(self) -> None:
        config = load_service_config({})

        self.assertFalse(config.internal_tokenized_endpoint_enabled)
        self.assertIsNone(config.pa_base_manifest_path)
        self.assertIsNone(config.pa_micro_manifest_path)

    def test_enabled_internal_endpoint_requires_explicit_manifest_paths(self) -> None:
        with self.assertRaises(ConfigurationError):
            ServiceConfig(
                environment="test",
                internal_tokenized_endpoint_enabled=True,
            )

        with self.assertRaises(ConfigurationError):
            load_service_config(
                {
                    "WATHIQ_ARASEG_INTERNAL_TOKENIZED_ENDPOINT_ENABLED": "true",
                    "WATHIQ_ARASEG_PA_BASE_MANIFEST_PATH": "  ",
                    "WATHIQ_ARASEG_PA_MICRO_MANIFEST_PATH": "models/pa/micro/manifest.json",
                }
            )


class InternalTokenizedEndpointTests(unittest.TestCase):
    def test_disabled_mode_does_not_build_pipeline_and_internal_route_is_unavailable(self) -> None:
        config = _build_config()

        with mock.patch.object(app_module, "build_pa_pipeline") as build_mock:
            with TestClient(create_app(config)) as client:
                response = client.post(
                    "/internal/api/v1/segment-tokenized",
                    json=_build_valid_internal_payload(),
                )

        self.assertEqual(response.status_code, 404)
        build_mock.assert_not_called()

    def test_enabled_mode_builds_pipeline_once_at_startup_with_explicit_paths_and_cpu(self) -> None:
        config = _build_config(enabled=True)
        pipeline = _RecordingInternalPipeline(_single_segment_output)

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            return_value=pipeline,
        ) as build_mock:
            app = create_app(config)
            with TestClient(app):
                self.assertIs(app.state.internal_pa_pipeline, pipeline)

        build_mock.assert_called_once_with(
            config.pa_base_manifest_path,
            config.pa_micro_manifest_path,
            device="cpu",
        )

    def test_enabled_startup_failure_fails_closed_with_controlled_error(self) -> None:
        config = _build_config(enabled=True)

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            side_effect=BaseRuntimeLoadError("bad base runtime"),
        ):
            app = create_app(config)
            with self.assertRaises(ApplicationStartupError) as context:
                with TestClient(app):
                    pass

        self.assertIsInstance(context.exception.__cause__, BaseRuntimeLoadError)

    def test_public_endpoint_remains_fake_and_does_not_call_internal_pipeline(self) -> None:
        config = _build_config(enabled=True)
        pipeline = _RecordingInternalPipeline(_single_segment_output)

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            return_value=pipeline,
        ):
            app = create_app(config)
            with mock.patch.object(
                pipeline,
                "segment",
                wraps=pipeline.segment,
            ) as internal_segment_mock, TestClient(app) as client:
                response = client.post(
                    "/api/v1/segment",
                    json={
                        "documentId": "doc-public",
                        "text": "نص عام",
                        "track": "PA",
                        "preserveParagraphs": True,
                        "returnConfidence": True,
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["modelVersion"], "fake-pa-contract-v1")
        internal_segment_mock.assert_not_called()

    def test_internal_endpoint_accepts_only_pa_and_maps_tokens_exactly(self) -> None:
        config = _build_config(enabled=True)
        pipeline = _RecordingInternalPipeline(_single_segment_output)
        payload = _build_valid_internal_payload()

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            return_value=pipeline,
        ):
            app = create_app(config)
            with mock.patch.object(
                app.state.segmentation_service,
                "segment",
                side_effect=AssertionError("Internal route must not use the public segmentation service."),
            ) as public_service_mock, TestClient(app) as client:
                response = client.post("/internal/api/v1/segment-tokenized", json=payload)

        self.assertEqual(response.status_code, 200)
        public_service_mock.assert_not_called()
        self.assertEqual(len(pipeline.requests), 1)
        domain_request = pipeline.requests[0]
        self.assertIsInstance(domain_request, SegmentationRequest)
        self.assertEqual(domain_request.document_id, payload["documentId"])
        self.assertEqual(domain_request.text, payload["text"])
        self.assertEqual(domain_request.track, "PA")
        self.assertEqual(
            domain_request.tokens,
            (
                SegmentationToken(index=0, text="هذا", start_offset=2, end_offset=5),
                SegmentationToken(index=1, text=".", start_offset=6, end_offset=7),
                SegmentationToken(index=2, text="نص", start_offset=8, end_offset=10),
                SegmentationToken(index=3, text="\n", start_offset=10, end_offset=11),
                SegmentationToken(index=4, text="\\n", start_offset=11, end_offset=13),
                SegmentationToken(index=5, text="[PAR]", start_offset=13, end_offset=18),
                SegmentationToken(index=6, text="!", start_offset=18, end_offset=19),
            ),
        )

    def test_internal_endpoint_preserves_exact_source_slices_and_special_content(self) -> None:
        config = _build_config(enabled=True)
        pipeline = _RecordingInternalPipeline(_multi_segment_output)

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            return_value=pipeline,
        ):
            with TestClient(create_app(config)) as client:
                response = client.post(
                    "/internal/api/v1/segment-tokenized",
                    json=_build_valid_internal_payload(),
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
                "pipelineId",
                "normalizedText",
                "segments",
            },
        )
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["provider"], "AraSeg")
        self.assertEqual(payload["track"], "PA")
        self.assertEqual(payload["pipelineId"], "pa-current-micro-ensemble-861752")
        self.assertEqual(payload["normalizedText"], _source_text())
        self.assertEqual(
            tuple(segment["text"] for segment in payload["segments"]),
            ("  هذا .", "\tنص\n", "\\n[PAR]!  "),
        )
        self.assertEqual("".join(segment["text"] for segment in payload["segments"]), _source_text())
        self.assertEqual(payload["segments"][0]["startToken"], 0)
        self.assertEqual(payload["segments"][0]["endToken"], 1)
        self.assertEqual(payload["segments"][1]["startToken"], 2)
        self.assertEqual(payload["segments"][1]["endToken"], 3)
        self.assertEqual(payload["segments"][2]["startToken"], 4)
        self.assertEqual(payload["segments"][2]["endToken"], 6)

    def test_invalid_tokenized_requests_return_structured_errors(self) -> None:
        cases = (
            ("missing tokens", _without_key(_build_valid_internal_payload(), "tokens"), 400, "INVALID_INPUT"),
            ("empty tokens", {**_build_valid_internal_payload(), "tokens": []}, 400, "INVALID_INPUT"),
            (
                "duplicate indexes",
                {
                    **_build_valid_internal_payload(),
                    "tokens": [
                        {"index": 0, "text": "هذا", "startOffset": 2, "endOffset": 5},
                        {"index": 0, "text": ".", "startOffset": 6, "endOffset": 7},
                    ],
                },
                400,
                "INVALID_INPUT",
            ),
            (
                "skipped indexes",
                {
                    **_build_valid_internal_payload(),
                    "tokens": [
                        {"index": 0, "text": "هذا", "startOffset": 2, "endOffset": 5},
                        {"index": 2, "text": ".", "startOffset": 6, "endOffset": 7},
                    ],
                },
                400,
                "INVALID_INPUT",
            ),
            (
                "overlapping spans",
                {
                    **_build_valid_internal_payload(),
                    "tokens": [
                        {"index": 0, "text": "هذا", "startOffset": 2, "endOffset": 5},
                        {"index": 1, "text": "ا.", "startOffset": 4, "endOffset": 6},
                    ],
                },
                400,
                "INVALID_INPUT",
            ),
            (
                "out of range span",
                {
                    **_build_valid_internal_payload(),
                    "tokens": [
                        {"index": 0, "text": "هذا", "startOffset": 2, "endOffset": 5},
                        {"index": 1, "text": ".", "startOffset": 6, "endOffset": 99},
                    ],
                },
                400,
                "INVALID_INPUT",
            ),
            (
                "source mismatch",
                {
                    **_build_valid_internal_payload(),
                    "tokens": [
                        {"index": 0, "text": "خطأ", "startOffset": 2, "endOffset": 5},
                    ],
                },
                400,
                "INVALID_INPUT",
            ),
            (
                "crlf text",
                {
                    **_build_valid_internal_payload(),
                    "text": "مرحبا\r\nالعالم",
                    "tokens": [{"index": 0, "text": "مرحبا", "startOffset": 0, "endOffset": 5}],
                },
                400,
                "INVALID_INPUT",
            ),
            (
                "bare cr text",
                {
                    **_build_valid_internal_payload(),
                    "text": "مرحبا\rالعالم",
                    "tokens": [{"index": 0, "text": "مرحبا", "startOffset": 0, "endOffset": 5}],
                },
                400,
                "INVALID_INPUT",
            ),
            ("non-pa track", {**_build_valid_internal_payload(), "track": "NP"}, 422, "UNSUPPORTED_TRACK"),
            ("extra field", {**_build_valid_internal_payload(), "extraField": True}, 400, "INVALID_INPUT"),
        )
        config = _build_config(enabled=True)
        pipeline = _RecordingInternalPipeline(_single_segment_output)

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            return_value=pipeline,
        ):
            with TestClient(create_app(config)) as client:
                for name, body, expected_status, expected_code in cases:
                    with self.subTest(name=name):
                        response = client.post("/internal/api/v1/segment-tokenized", json=body)
                        payload = response.json()
                        self.assertEqual(response.status_code, expected_status)
                        self.assertEqual(payload["error"]["code"], expected_code)
                        self.assertTrue(payload["error"]["requestId"])

    def test_same_pipeline_instance_is_reused_across_internal_requests(self) -> None:
        config = _build_config(enabled=True)
        pipeline = _RecordingInternalPipeline(_single_segment_output)
        payload = _build_valid_internal_payload()

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            return_value=pipeline,
        ) as build_mock:
            app = create_app(config)
            with TestClient(app) as client:
                first = client.post("/internal/api/v1/segment-tokenized", json=payload)
                second = client.post("/internal/api/v1/segment-tokenized", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        build_mock.assert_called_once()
        self.assertEqual(len(pipeline.requests), 2)
        self.assertIs(app.state.internal_pa_pipeline, pipeline)

    def test_internal_pipeline_failures_are_mapped_without_fallback(self) -> None:
        config = _build_config(enabled=True)
        payload = _build_valid_internal_payload()
        failing_messages = (
            "inference failed",
            "post-processing failed",
            "source rendering failed",
        )

        for message in failing_messages:
            with self.subTest(message=message):
                pipeline = _RecordingInternalPipeline(
                    _single_segment_output,
                    exception=InvalidSegmentationResultError(message),
                )

                with mock.patch.object(
                    app_module,
                    "build_pa_pipeline",
                    return_value=pipeline,
                ):
                    app = create_app(config)
                    with mock.patch.object(
                        app.state.segmentation_service,
                        "segment",
                        side_effect=AssertionError("Internal route must not fall back to FakeSegmentationPipeline."),
                    ) as public_service_mock, TestClient(app) as client:
                        response = client.post("/internal/api/v1/segment-tokenized", json=payload)

                self.assertEqual(response.status_code, 500)
                self.assertEqual(response.json()["error"]["code"], "INFERENCE_FAILED")
                self.assertNotIn("C:\\", response.text)
                self.assertNotIn("Traceback", response.text)
                public_service_mock.assert_not_called()

    def test_internal_route_source_contains_no_tokenization_or_pa_rule_duplication(self) -> None:
        route_source = Path(SRC_ROOT / "wathiq_araseg" / "api" / "segmentation.py").read_text(
            encoding="utf-8"
        )
        app_source = Path(SRC_ROOT / "wathiq_araseg" / "app.py").read_text(encoding="utf-8")

        for forbidden_snippet in (
            "str.split(",
            "splitlines(",
            "re.",
            "AutoTokenizer",
            "AutoModel",
            "0.543",
            "0.310",
            '[".", "؟", "?", "!", "…"]',
        ):
            with self.subTest(forbidden_snippet=forbidden_snippet):
                self.assertNotIn(forbidden_snippet, route_source)
                self.assertNotIn(forbidden_snippet, app_source)


class InternalTokenizedRealIntegrationTests(unittest.TestCase):
    def test_real_internal_endpoint_runs_offline_and_reuses_one_pipeline(self) -> None:
        base_manifest_path = SERVICE_ROOT / "models" / "pa" / "manifest.json"
        micro_manifest_path = SERVICE_ROOT / "models" / "pa" / "micro" / "manifest.json"
        base_artifact_root = SERVICE_ROOT / "models" / "pa" / "best_model"
        micro_artifact_root = SERVICE_ROOT / "models" / "pa" / "micro" / "best_model"

        if not base_artifact_root.is_dir() or not micro_artifact_root.is_dir():
            self.skipTest("Local PA base or micro best_model directory is not present.")

        app = create_app(
            _build_config(
                enabled=True,
                pa_base_manifest_path=base_manifest_path,
                pa_micro_manifest_path=micro_manifest_path,
            )
        )
        payload = _build_valid_internal_payload()
        start_time = time.perf_counter()

        with TestClient(app) as client:
            pipeline = client.app.state.internal_pa_pipeline
            self.assertIsNotNone(pipeline)
            self.assertEqual(pipeline.track, "PA")
            self.assertEqual(pipeline.pipeline_id, "pa-current-micro-ensemble-861752")

            with mock.patch.object(pipeline, "segment", wraps=pipeline.segment) as segment_mock:
                first = client.post("/internal/api/v1/segment-tokenized", json=payload)
                second = client.post("/internal/api/v1/segment-tokenized", json=payload)
                public = client.post(
                    "/api/v1/segment",
                    json={
                        "documentId": "doc-public",
                        "text": "نص عام",
                        "track": "PA",
                        "preserveParagraphs": True,
                        "returnConfidence": True,
                    },
                )

            self.assertEqual(segment_mock.call_count, 2)
            self.assertIs(client.app.state.internal_pa_pipeline, pipeline)

        wall_clock_duration = time.perf_counter() - start_time

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.json()["modelVersion"], "fake-pa-contract-v1")
        self.assertEqual(
            "".join(segment["text"] for segment in first.json()["segments"]),
            payload["text"],
        )
        self.assertIn("\n", first.json()["normalizedText"])
        self.assertIn("\\n", first.json()["normalizedText"])
        self.assertIn("[PAR]", first.json()["normalizedText"])
        self.assertGreater(wall_clock_duration, 0.0)

        direct_request = SegmentationRequest(
            document_id=payload["documentId"],
            text=payload["text"],
            track=payload["track"],
            tokens=tuple(
                SegmentationToken(
                    index=token["index"],
                    text=token["text"],
                    start_offset=token["startOffset"],
                    end_offset=token["endOffset"],
                )
                for token in payload["tokens"]
            ),
        )
        direct_result = pipeline.segment(direct_request)
        self.assertEqual(
            tuple(segment["text"] for segment in first.json()["segments"]),
            tuple(segment.text for segment in direct_result.segments),
        )


class _RecordingInternalPipeline(AbstractSegmentationPipeline):
    @property
    def track(self) -> str:
        return "PA"

    @property
    def pipeline_id(self) -> str:
        return "pa-current-micro-ensemble-861752"

    def __init__(
        self,
        raw_segments_factory,
        *,
        exception: Exception | None = None,
    ) -> None:
        self._raw_segments_factory = raw_segments_factory
        self._exception = exception
        self.requests: list[SegmentationRequest] = []

    def _run_pipeline(self, request: SegmentationRequest):
        self.requests.append(request)
        if self._exception is not None:
            raise self._exception
        return self._raw_segments_factory(request)


def _single_segment_output(request: SegmentationRequest) -> tuple[str, ...]:
    return (request.text,)


def _multi_segment_output(_request: SegmentationRequest) -> tuple[str, ...]:
    return ("  هذا .", "\tنص\n", "\\n[PAR]!  ")


def _source_text() -> str:
    return "  هذا .\tنص\n\\n[PAR]!  "


def _build_valid_internal_payload() -> dict[str, object]:
    return {
        "documentId": "doc-tokenized",
        "text": _source_text(),
        "track": "PA",
        "tokens": [
            {"index": 0, "text": "هذا", "startOffset": 2, "endOffset": 5},
            {"index": 1, "text": ".", "startOffset": 6, "endOffset": 7},
            {"index": 2, "text": "نص", "startOffset": 8, "endOffset": 10},
            {"index": 3, "text": "\n", "startOffset": 10, "endOffset": 11},
            {"index": 4, "text": "\\n", "startOffset": 11, "endOffset": 13},
            {"index": 5, "text": "[PAR]", "startOffset": 13, "endOffset": 18},
            {"index": 6, "text": "!", "startOffset": 18, "endOffset": 19},
        ],
    }


def _without_key(payload: dict[str, object], key: str) -> dict[str, object]:
    return {name: value for name, value in payload.items() if name != key}


def _build_config(
    *,
    enabled: bool = False,
    pa_base_manifest_path: Path | None = Path("models/pa/manifest.json"),
    pa_micro_manifest_path: Path | None = Path("models/pa/micro/manifest.json"),
) -> ServiceConfig:
    return ServiceConfig(
        service_name="wathiq-araseg-service",
        service_version="0.1.0",
        environment="test",
        host="127.0.0.1",
        port=8000,
        log_level="INFO",
        inference_device="cpu",
        internal_tokenized_endpoint_enabled=enabled,
        pa_base_manifest_path=pa_base_manifest_path,
        pa_micro_manifest_path=pa_micro_manifest_path,
    )


if __name__ == "__main__":
    unittest.main()
