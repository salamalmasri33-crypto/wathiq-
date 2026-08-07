from __future__ import annotations

import inspect
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.app import create_app  # noqa: E402
from wathiq_araseg.config import ServiceConfig  # noqa: E402
from wathiq_araseg.segmentation import (  # noqa: E402
    AbstractSegmentationPipeline,
    PipelineRegistry,
    SegmentationRequest,
    SentenceSegmentationService,
)


class SentenceSegmentationServiceTests(unittest.TestCase):
    def test_service_depends_on_registry_and_abstraction(self) -> None:
        registry = PipelineRegistry([_ReplacementPipeline()])
        service = SentenceSegmentationService(registry)
        request = SegmentationRequest(
            document_id="doc-001",
            text="نص للاختبار",
            track="PA",
        )

        with mock.patch.object(registry, "resolve", wraps=registry.resolve) as resolve_mock:
            result = service.segment(request)

        resolve_mock.assert_called_once_with("PA")
        self.assertEqual(result.pipeline_id, "replacement-pa-pipeline")
        self.assertEqual(result.track, "PA")

    def test_second_pipeline_implementation_can_replace_fake_pipeline(self) -> None:
        registry = PipelineRegistry([_AlternativePipeline()])
        service = SentenceSegmentationService(registry)

        result = service.segment(
            SegmentationRequest(
                document_id="doc-002",
                text="هذا بديل",
                track="PA",
            )
        )

        self.assertEqual(result.pipeline_id, "alternative-pa-pipeline")
        self.assertEqual(tuple(segment.text for segment in result.segments), ("هذا", " بديل"))

    def test_service_does_not_instantiate_fake_pipeline_directly(self) -> None:
        registry = PipelineRegistry([_ReplacementPipeline()])
        service = SentenceSegmentationService(registry)

        with mock.patch(
            "wathiq_araseg.segmentation.fake_pipeline.FakeSegmentationPipeline",
            side_effect=AssertionError("Fake pipeline must not be instantiated by the service."),
        ):
            result = service.segment(
                SegmentationRequest(
                    document_id="doc-003",
                    text="نص الخدمة",
                    track="PA",
                )
            )

        self.assertEqual(result.pipeline_id, "replacement-pa-pipeline")
        self.assertNotIn(
            "FakeSegmentationPipeline",
            inspect.getsource(SentenceSegmentationService),
        )

    def test_segmentation_modules_do_not_load_fastapi_or_model_runtime_dependencies(self) -> None:
        script = """
import json
import sys
from pathlib import Path

service_root = Path.cwd()
src_root = service_root / "src"
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from wathiq_araseg.segmentation.service import SentenceSegmentationService
from wathiq_araseg.segmentation.registry import PipelineRegistry
from wathiq_araseg.segmentation.fake_pipeline import FakeSegmentationPipeline

print(json.dumps({
    "fastapi_loaded": "fastapi" in sys.modules,
    "torch_loaded": "torch" in sys.modules,
    "transformers_loaded": "transformers" in sys.modules,
    "model_loader_loaded": "wathiq_araseg.runtime.model_loader" in sys.modules,
    "service_name": SentenceSegmentationService.__name__,
    "registry_name": PipelineRegistry.__name__,
    "pipeline_name": FakeSegmentationPipeline.__name__,
}, ensure_ascii=True))
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            cwd=SERVICE_ROOT,
            text=True,
        )

        payload = json.loads(completed.stdout)

        self.assertFalse(payload["fastapi_loaded"])
        self.assertFalse(payload["torch_loaded"])
        self.assertFalse(payload["transformers_loaded"])
        self.assertFalse(payload["model_loader_loaded"])


class ApplicationBoundaryTests(unittest.TestCase):
    def test_health_response_remains_unchanged(self) -> None:
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

    def test_application_route_inventory_remains_unchanged(self) -> None:
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


class _ReplacementPipeline(AbstractSegmentationPipeline):
    @property
    def track(self) -> str:
        return "PA"

    @property
    def pipeline_id(self) -> str:
        return "replacement-pa-pipeline"

    def _run_pipeline(self, request: SegmentationRequest) -> tuple[str, ...]:
        return (request.text,)


class _AlternativePipeline(AbstractSegmentationPipeline):
    @property
    def track(self) -> str:
        return "PA"

    @property
    def pipeline_id(self) -> str:
        return "alternative-pa-pipeline"

    def _run_pipeline(self, request: SegmentationRequest) -> tuple[str, ...]:
        return ("هذا", " بديل")


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
