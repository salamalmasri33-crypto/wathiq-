from __future__ import annotations

import inspect
from pathlib import Path
import sys
import unittest
from unittest import mock

from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg import app as app_module  # noqa: E402
from wathiq_araseg.app import create_app  # noqa: E402
from wathiq_araseg.config import ConfigurationError, ServiceConfig  # noqa: E402
from wathiq_araseg.segmentation import (  # noqa: E402
    AbstractSegmentationPipeline,
    InvalidSegmentationResultError,
    LosslessUnicodeTokenSpanProvider,
    RawTextSegmentationService,
    RawTextTokenSpanProvider,
    SegmentationRequest,
    SegmentationToken,
)


class InternalRawTextConfigurationTests(unittest.TestCase):
    def test_enabled_internal_pa_endpoints_require_both_manifest_paths(self) -> None:
        with self.assertRaises(ConfigurationError):
            ServiceConfig(
                environment="test",
                internal_tokenized_endpoint_enabled=True,
                pa_base_manifest_path=Path("models/pa/manifest.json"),
                pa_micro_manifest_path=None,
            )

        with self.assertRaises(ConfigurationError):
            ServiceConfig(
                environment="test",
                internal_tokenized_endpoint_enabled=True,
                pa_base_manifest_path=None,
                pa_micro_manifest_path=Path("models/pa/micro/manifest.json"),
            )


class InternalRawTextEndpointTests(unittest.TestCase):
    def test_disabled_mode_keeps_raw_route_absent_and_builds_no_real_dependencies(self) -> None:
        config = _build_config()

        with mock.patch.object(app_module, "build_pa_pipeline") as build_mock, mock.patch.object(
            app_module,
            "LosslessUnicodeTokenSpanProvider",
        ) as provider_mock, mock.patch.object(
            app_module,
            "RawTextSegmentationService",
        ) as raw_service_mock:
            with TestClient(create_app(config)) as client:
                response = client.post(
                    "/internal/api/v1/segment-text",
                    json=_build_valid_raw_payload(),
                )

        self.assertEqual(response.status_code, 404)
        build_mock.assert_not_called()
        provider_mock.assert_not_called()
        raw_service_mock.assert_not_called()

    def test_enabled_mode_builds_pipeline_provider_and_raw_service_once(self) -> None:
        config = _build_config(enabled=True)
        pipeline = _RecordingPipeline(_single_segment_output)
        provider = mock.Mock(spec=LosslessUnicodeTokenSpanProvider)
        raw_service = mock.Mock(spec=RawTextSegmentationService)

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            return_value=pipeline,
        ) as build_mock, mock.patch.object(
            app_module,
            "LosslessUnicodeTokenSpanProvider",
            return_value=provider,
        ) as provider_mock, mock.patch.object(
            app_module,
            "RawTextSegmentationService",
            return_value=raw_service,
        ) as raw_service_mock:
            app = create_app(config)
            with TestClient(app):
                self.assertIs(app.state.internal_pa_pipeline, pipeline)
                self.assertIs(app.state.internal_pa_token_span_provider, provider)
                self.assertIs(app.state.internal_pa_raw_text_service, raw_service)

        build_mock.assert_called_once_with(
            config.pa_base_manifest_path,
            config.pa_micro_manifest_path,
            device="cpu",
        )
        provider_mock.assert_called_once_with()
        raw_service_mock.assert_called_once_with(
            token_span_provider=provider,
            segmentation_pipeline=pipeline,
        )

    def test_raw_route_calls_service_once_per_request_and_reuses_same_service_and_pipeline(self) -> None:
        config = _build_config(enabled=True)
        pipeline = _RecordingPipeline(_single_segment_output)
        raw_payload = _build_valid_raw_payload()
        tokenized_payload = _build_tokenized_payload_from_text(
            raw_payload["text"],
            document_id=raw_payload["documentId"],
        )
        provider = _RecordingTokenSpanProvider(
            LosslessUnicodeTokenSpanProvider().provide(raw_payload["text"])
        )

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            return_value=pipeline,
        ), mock.patch.object(
            app_module,
            "LosslessUnicodeTokenSpanProvider",
            return_value=provider,
        ):
            app = create_app(config)
            with TestClient(app) as client:
                service = client.app.state.internal_pa_raw_text_service
                self.assertIsNotNone(service)
                self.assertIs(client.app.state.internal_pa_pipeline, pipeline)
                self.assertIs(client.app.state.internal_pa_token_span_provider, provider)

                with mock.patch.object(
                    service,
                    "segment_with_tokens",
                    wraps=service.segment_with_tokens,
                ) as service_mock, mock.patch.object(
                    pipeline,
                    "segment",
                    wraps=pipeline.segment,
                ) as pipeline_mock:
                    first = client.post("/internal/api/v1/segment-text", json=raw_payload)
                    second = client.post("/internal/api/v1/segment-text", json=raw_payload)
                    tokenized = client.post(
                        "/internal/api/v1/segment-tokenized",
                        json=tokenized_payload,
                    )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(tokenized.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(service_mock.call_count, 2)
        self.assertEqual(pipeline_mock.call_count, 3)
        self.assertEqual(provider.calls, [raw_payload["text"], raw_payload["text"]])

    def test_public_endpoint_remains_fake_and_raw_route_does_not_use_public_service(self) -> None:
        config = _build_config(enabled=True)
        pipeline = _RecordingPipeline(_single_segment_output)

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            return_value=pipeline,
        ):
            app = create_app(config)
            with mock.patch.object(
                app.state.segmentation_service,
                "segment",
                wraps=app.state.segmentation_service.segment,
            ) as public_service_mock, TestClient(app) as client:
                raw_response = client.post(
                    "/internal/api/v1/segment-text",
                    json=_build_valid_raw_payload(),
                )
                self.assertEqual(public_service_mock.call_count, 0)
                public_response = client.post(
                    "/api/v1/segment",
                    json={
                        "documentId": "doc-public",
                        "text": "نص عام",
                        "track": "PA",
                        "preserveParagraphs": True,
                        "returnConfidence": True,
                    },
                )

        self.assertEqual(raw_response.status_code, 200)
        self.assertEqual(public_response.status_code, 200)
        self.assertEqual(public_response.json()["modelVersion"], "fake-pa-contract-v1")
        self.assertEqual(public_service_mock.call_count, 1)

    def test_raw_route_with_real_provider_passes_expected_tokens_into_pipeline(self) -> None:
        config = _build_config(enabled=True)
        pipeline = _RecordingPipeline(_single_segment_output)
        source = "صدر القرار رقم 25. يبدأ التنفيذ غداً."

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            return_value=pipeline,
        ):
            with TestClient(create_app(config)) as client:
                response = client.post(
                    "/internal/api/v1/segment-text",
                    json=_build_valid_raw_payload(text=source),
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(pipeline.requests), 1)
        request_tokens = pipeline.requests[0].tokens or ()
        self.assertEqual(
            tuple(token.text for token in request_tokens),
            ("صدر", "القرار", "رقم", "25", ".", "يبدأ", "التنفيذ", "غداً", "."),
        )
        for token in request_tokens:
            self.assertEqual(source[token.start_offset : token.end_offset], token.text)

    def test_raw_route_uses_provider_once_and_forwards_exact_tuple_identity(self) -> None:
        config = _build_config(enabled=True)
        source = "صدر القرار رقم 25. يبدأ التنفيذ غداً."
        produced_tokens = LosslessUnicodeTokenSpanProvider().provide(source)
        provider = _RecordingTokenSpanProvider(produced_tokens)
        pipeline = _RecordingPipeline(_single_segment_output)

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            return_value=pipeline,
        ), mock.patch.object(
            app_module,
            "LosslessUnicodeTokenSpanProvider",
            return_value=provider,
        ):
            app = create_app(config)
            with TestClient(app) as client:
                service = client.app.state.internal_pa_raw_text_service
                self.assertIsNotNone(service)
                self.assertIs(client.app.state.internal_pa_token_span_provider, provider)

                with mock.patch.object(
                    service,
                    "segment_with_tokens",
                    wraps=service.segment_with_tokens,
                ) as service_mock, mock.patch.object(
                    pipeline,
                    "segment",
                    wraps=pipeline.segment,
                ) as pipeline_mock:
                    response = client.post(
                        "/internal/api/v1/segment-text",
                        json=_build_valid_raw_payload(text=source),
                    )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(provider.calls, [source])
        self.assertEqual(service_mock.call_count, 1)
        self.assertEqual(pipeline_mock.call_count, 1)
        self.assertEqual(len(pipeline.requests), 1)
        self.assertIs(pipeline.requests[0].tokens, produced_tokens)

    def test_raw_route_preserves_exact_source_and_special_content(self) -> None:
        config = _build_config(enabled=True)
        pipeline = _RecordingPipeline(_single_segment_output)
        source = "  قبل\tنص\n\\n[PAR] بعد؟  "

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            return_value=pipeline,
        ):
            with TestClient(create_app(config)) as client:
                response = client.post(
                    "/internal/api/v1/segment-text",
                    json=_build_valid_raw_payload(text=source),
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["normalizedText"], source)
        self.assertEqual("".join(segment["text"] for segment in payload["segments"]), source)
        self.assertIn("\n", payload["normalizedText"])
        self.assertIn("\\n", payload["normalizedText"])
        self.assertIn("[PAR]", payload["normalizedText"])
        self.assertIn("؟", payload["normalizedText"])

    def test_raw_route_rejects_unsupported_track_and_extra_fields(self) -> None:
        config = _build_config(enabled=True)
        pipeline = _RecordingPipeline(_single_segment_output)
        cases = (
            ("unsupported track", {**_build_valid_raw_payload(), "track": "NP"}, 422, "UNSUPPORTED_TRACK"),
            ("extra tokens", {**_build_valid_raw_payload(), "tokens": []}, 400, "INVALID_INPUT"),
            ("extra offsets", {**_build_valid_raw_payload(), "startOffset": 0}, 400, "INVALID_INPUT"),
        )

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            return_value=pipeline,
        ):
            with TestClient(create_app(config)) as client:
                for name, body, expected_status, expected_code in cases:
                    with self.subTest(name=name):
                        response = client.post("/internal/api/v1/segment-text", json=body)
                        payload = response.json()
                        self.assertEqual(response.status_code, expected_status)
                        self.assertEqual(payload["error"]["code"], expected_code)

    def test_raw_route_translates_domain_failures_without_leaking_details(self) -> None:
        config = _build_config(enabled=True)
        pipeline = _RecordingPipeline(_single_segment_output)
        cases = (
            ("empty text", "", 400, "INVALID_INPUT", 0),
            ("whitespace only", " \t  ", 400, "INVALID_INPUT", 0),
            ("cr text", "مرحبا\rالعالم", 400, "INVALID_INPUT", 0),
            ("crlf text", "مرحبا\r\nالعالم", 400, "INVALID_INPUT", 0),
        )

        with mock.patch.object(
            app_module,
            "build_pa_pipeline",
            return_value=pipeline,
        ):
            with TestClient(create_app(config)) as client:
                for name, text, expected_status, expected_code, expected_pipeline_calls in cases:
                    with self.subTest(name=name):
                        pipeline.requests.clear()
                        response = client.post(
                            "/internal/api/v1/segment-text",
                            json=_build_valid_raw_payload(text=text),
                        )
                        payload = response.json()
                        self.assertEqual(response.status_code, expected_status)
                        self.assertEqual(payload["error"]["code"], expected_code)
                        self.assertNotIn("C:\\", response.text)
                        self.assertNotIn("models/pa", response.text)
                        self.assertNotIn("Traceback", response.text)
                        self.assertEqual(len(pipeline.requests), expected_pipeline_calls)

    def test_raw_route_source_contains_no_registry_or_fake_or_scanner_logic(self) -> None:
        route_source = inspect.getsource(app_module)
        segmentation_module_source = Path(
            SRC_ROOT / "wathiq_araseg" / "api" / "segmentation.py"
        ).read_text(encoding="utf-8")

        for forbidden_fragment in (
            "PipelineRegistry",
            "FakeSegmentationPipeline",
            "str.split(",
            "splitlines(",
            "unicodedata",
            "AutoTokenizer",
            "AutoModel",
        ):
            with self.subTest(forbidden_fragment=forbidden_fragment):
                self.assertNotIn(forbidden_fragment, inspect.getsource(_route_source_probe))
                self.assertNotIn(forbidden_fragment, segmentation_module_source.split("def segment_raw_text", 1)[1])


class InternalRawTextRealIntegrationTests(unittest.TestCase):
    def test_real_raw_text_endpoint_runs_offline_and_reuses_one_service(self) -> None:
        base_manifest_path = SERVICE_ROOT / "models" / "pa" / "manifest.json"
        micro_manifest_path = SERVICE_ROOT / "models" / "pa" / "micro" / "manifest.json"
        base_artifact_root = SERVICE_ROOT / "models" / "pa" / "best_model"
        micro_artifact_root = SERVICE_ROOT / "models" / "pa" / "micro" / "best_model"

        if not base_artifact_root.is_dir() or not micro_artifact_root.is_dir():
            self.skipTest("Local PA base or micro best_model directory is not present.")

        source = "صدر القرار رقم 25.\nيبدأ التنفيذ غداً.\\n[PAR]"
        raw_payload = _build_valid_raw_payload(text=source, document_id="doc-real-raw")
        tokenized_payload = _build_tokenized_payload_from_text(
            source,
            document_id="doc-real-raw",
        )
        app = create_app(
            _build_config(
                enabled=True,
                pa_base_manifest_path=base_manifest_path,
                pa_micro_manifest_path=micro_manifest_path,
            )
        )

        with TestClient(app) as client:
            service = client.app.state.internal_pa_raw_text_service
            pipeline = client.app.state.internal_pa_pipeline
            provider = client.app.state.internal_pa_token_span_provider
            self.assertIsNotNone(service)
            self.assertIsNotNone(pipeline)
            self.assertIsNotNone(provider)
            self.assertIs(service._token_span_provider, provider)

            with mock.patch.object(service, "segment_with_tokens", wraps=service.segment_with_tokens) as service_mock, mock.patch.object(
                provider,
                "provide",
                wraps=provider.provide,
            ) as provider_mock, mock.patch.object(
                pipeline,
                "segment",
                wraps=pipeline.segment,
            ) as pipeline_mock:
                first = client.post("/internal/api/v1/segment-text", json=raw_payload)
                second = client.post("/internal/api/v1/segment-text", json=raw_payload)
                tokenized = client.post(
                    "/internal/api/v1/segment-tokenized",
                    json=tokenized_payload,
                )
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

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(tokenized.status_code, 200)
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.json()["modelVersion"], "fake-pa-contract-v1")
        self.assertEqual(first.json(), second.json())
        self.assertEqual(service_mock.call_count, 2)
        self.assertEqual(provider_mock.call_count, 2)
        self.assertEqual(pipeline_mock.call_count, 3)
        self.assertEqual(
            "".join(segment["text"] for segment in first.json()["segments"]),
            source,
        )
        self.assertIn("\n", first.json()["normalizedText"])
        self.assertIn("\\n", first.json()["normalizedText"])
        self.assertIn("[PAR]", first.json()["normalizedText"])


class _RecordingPipeline(AbstractSegmentationPipeline):
    @property
    def track(self) -> str:
        return "PA"

    @property
    def pipeline_id(self) -> str:
        return "pa-current-micro-ensemble-861752"

    def __init__(self, raw_segments_factory, *, exception: Exception | None = None) -> None:
        self._raw_segments_factory = raw_segments_factory
        self._exception = exception
        self.requests: list[SegmentationRequest] = []

    def _run_pipeline(self, request: SegmentationRequest):
        self.requests.append(request)
        if self._exception is not None:
            raise self._exception
        return self._raw_segments_factory(request)


class _RecordingTokenSpanProvider(RawTextTokenSpanProvider):
    def __init__(self, tokens: tuple[SegmentationToken, ...]) -> None:
        self._tokens = tokens
        self.calls: list[str] = []

    def provide(self, source_text: str) -> tuple[SegmentationToken, ...]:
        self.calls.append(source_text)
        return self._tokens


def _single_segment_output(request: SegmentationRequest) -> tuple[str, ...]:
    return (request.text,)


def _build_valid_raw_payload(
    *,
    text: str = "صدر القرار رقم 25. يبدأ التنفيذ غداً.",
    document_id: str = "doc-raw",
) -> dict[str, object]:
    return {
        "documentId": document_id,
        "text": text,
        "track": "PA",
    }


def _build_tokenized_payload_from_text(
    text: str,
    *,
    document_id: str,
) -> dict[str, object]:
    provider = LosslessUnicodeTokenSpanProvider()
    tokens = provider.provide(text)

    return {
        "documentId": document_id,
        "text": text,
        "track": "PA",
        "tokens": [
            {
                "index": token.index,
                "text": token.text,
                "startOffset": token.start_offset,
                "endOffset": token.end_offset,
            }
            for token in tokens
        ],
    }


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


def _route_source_probe() -> None:
    from wathiq_araseg.api.segmentation import segment_raw_text

    return segment_raw_text  # pragma: no cover


if __name__ == "__main__":
    unittest.main()
