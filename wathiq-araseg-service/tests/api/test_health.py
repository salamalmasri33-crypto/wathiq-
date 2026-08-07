from __future__ import annotations

from pathlib import Path
import socket
import sys
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.app import create_app  # noqa: E402
from wathiq_araseg.config import ConfigurationError, ServiceConfig  # noqa: E402


class AppFactoryTests(unittest.TestCase):
    def test_application_creation_succeeds(self) -> None:
        app = create_app(self._build_config())

        self.assertIsInstance(app, FastAPI)
        self.assertEqual(app.title, "wathiq-araseg-service")
        self.assertEqual(app.version, "0.1.0")

    def test_health_endpoint_returns_expected_payload(self) -> None:
        with TestClient(create_app(self._build_config())) as client:
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

    def test_health_endpoint_returns_configured_version_and_device(self) -> None:
        config = self._build_config(service_version="2.4.1", inference_device="cuda")

        with TestClient(create_app(config)) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], "2.4.1")
        self.assertEqual(response.json()["device"], "cuda")
        self.assertFalse(response.json()["modelReady"])

    def test_openapi_and_swagger_are_available(self) -> None:
        with TestClient(create_app(self._build_config())) as client:
            openapi_response = client.get("/openapi.json")
            docs_response = client.get("/docs")

        self.assertEqual(openapi_response.status_code, 200)
        self.assertIn("/health", openapi_response.json()["paths"])
        self.assertEqual(docs_response.status_code, 200)
        self.assertIn("Swagger UI", docs_response.text)

    def test_invalid_configuration_fails_clearly(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"WATHIQ_ARASEG_PORT": "not-a-number"},
            clear=True,
        ):
            with self.assertRaises(ConfigurationError) as context:
                create_app()

        self.assertIn("WATHIQ_ARASEG_PORT", str(context.exception))

    def test_model_loader_is_not_called_during_app_creation_or_health(self) -> None:
        config = self._build_config()

        with mock.patch(
            "wathiq_araseg.runtime.model_loader.load_local_model_runtime",
            side_effect=AssertionError("Model loader must not be called."),
        ) as load_model_mock:
            with TestClient(create_app(config)) as client:
                response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        load_model_mock.assert_not_called()

    def test_no_network_access_is_required_for_health_request(self) -> None:
        config = self._build_config()

        with mock.patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("Health requests must not open network connections."),
        ):
            with TestClient(create_app(config)) as client:
                response = client.get("/health")

        self.assertEqual(response.status_code, 200)

    @staticmethod
    def _build_config(
        *,
        service_name: str = "wathiq-araseg-service",
        service_version: str = "0.1.0",
        environment: str = "test",
        host: str = "127.0.0.1",
        port: int = 8000,
        log_level: str = "INFO",
        inference_device: str = "cpu",
    ) -> ServiceConfig:
        return ServiceConfig(
            service_name=service_name,
            service_version=service_version,
            environment=environment,
            host=host,
            port=port,
            log_level=log_level,
            inference_device=inference_device,
        )


if __name__ == "__main__":
    unittest.main()
