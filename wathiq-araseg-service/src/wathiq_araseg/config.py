"""Typed environment-based configuration for the Wathiq AraSeg service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Literal

from wathiq_araseg import __version__

EnvironmentName = Literal["development", "test", "production"]
LogLevelName = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
InferenceDeviceName = Literal["cpu", "cuda"]

ENV_PREFIX = "WATHIQ_ARASEG_"
SERVICE_NAME_ENV = f"{ENV_PREFIX}SERVICE_NAME"
SERVICE_VERSION_ENV = f"{ENV_PREFIX}SERVICE_VERSION"
ENVIRONMENT_ENV = f"{ENV_PREFIX}ENVIRONMENT"
HOST_ENV = f"{ENV_PREFIX}HOST"
PORT_ENV = f"{ENV_PREFIX}PORT"
LOG_LEVEL_ENV = f"{ENV_PREFIX}LOG_LEVEL"
INFERENCE_DEVICE_ENV = f"{ENV_PREFIX}INFERENCE_DEVICE"
INTERNAL_TOKENIZED_ENDPOINT_ENABLED_ENV = (
    f"{ENV_PREFIX}INTERNAL_TOKENIZED_ENDPOINT_ENABLED"
)
PA_BASE_MANIFEST_PATH_ENV = f"{ENV_PREFIX}PA_BASE_MANIFEST_PATH"
PA_MICRO_MANIFEST_PATH_ENV = f"{ENV_PREFIX}PA_MICRO_MANIFEST_PATH"

_ALLOWED_ENVIRONMENTS = ("development", "test", "production")
_ALLOWED_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_ALLOWED_INFERENCE_DEVICES = ("cpu", "cuda")

DEFAULT_SERVICE_NAME = "wathiq-araseg-service"
DEFAULT_SERVICE_VERSION = __version__
DEFAULT_ENVIRONMENT = "development"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_INFERENCE_DEVICE = "cpu"
DEFAULT_INTERNAL_TOKENIZED_ENDPOINT_ENABLED = False


class ConfigurationError(ValueError):
    """Raised when service configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class ServiceConfig:
    """Typed service configuration resolved from environment variables."""

    service_name: str = DEFAULT_SERVICE_NAME
    service_version: str = DEFAULT_SERVICE_VERSION
    environment: EnvironmentName = DEFAULT_ENVIRONMENT
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    log_level: LogLevelName = DEFAULT_LOG_LEVEL
    inference_device: InferenceDeviceName = DEFAULT_INFERENCE_DEVICE
    internal_tokenized_endpoint_enabled: bool = (
        DEFAULT_INTERNAL_TOKENIZED_ENDPOINT_ENABLED
    )
    pa_base_manifest_path: Path | None = None
    pa_micro_manifest_path: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "service_name",
            _normalize_non_empty_string("service_name", self.service_name),
        )
        object.__setattr__(
            self,
            "service_version",
            _normalize_non_empty_string("service_version", self.service_version),
        )
        object.__setattr__(
            self,
            "environment",
            _normalize_choice(
                "environment",
                self.environment,
                _ALLOWED_ENVIRONMENTS,
                normalize_to="lower",
            ),
        )
        object.__setattr__(self, "host", _normalize_non_empty_string("host", self.host))
        object.__setattr__(self, "port", _normalize_port(self.port))
        object.__setattr__(
            self,
            "log_level",
            _normalize_choice(
                "log_level",
                self.log_level,
                _ALLOWED_LOG_LEVELS,
                normalize_to="upper",
            ),
        )
        object.__setattr__(
            self,
            "inference_device",
            _normalize_choice(
                "inference_device",
                self.inference_device,
                _ALLOWED_INFERENCE_DEVICES,
                normalize_to="lower",
            ),
        )
        object.__setattr__(
            self,
            "internal_tokenized_endpoint_enabled",
            _normalize_bool(
                "internal_tokenized_endpoint_enabled",
                self.internal_tokenized_endpoint_enabled,
            ),
        )
        object.__setattr__(
            self,
            "pa_base_manifest_path",
            _normalize_optional_path("pa_base_manifest_path", self.pa_base_manifest_path),
        )
        object.__setattr__(
            self,
            "pa_micro_manifest_path",
            _normalize_optional_path(
                "pa_micro_manifest_path",
                self.pa_micro_manifest_path,
            ),
        )

        if self.internal_tokenized_endpoint_enabled and self.pa_base_manifest_path is None:
            raise ConfigurationError(
                "pa_base_manifest_path is required when the internal PA endpoints are enabled."
            )
        if self.internal_tokenized_endpoint_enabled and self.pa_micro_manifest_path is None:
            raise ConfigurationError(
                "pa_micro_manifest_path is required when the internal PA endpoints are enabled."
            )


def load_service_config(environ: Mapping[str, str] | None = None) -> ServiceConfig:
    """Load and validate service configuration from environment variables."""

    env = os.environ if environ is None else environ

    return ServiceConfig(
        service_name=_read_string(env, SERVICE_NAME_ENV, DEFAULT_SERVICE_NAME),
        service_version=_read_string(env, SERVICE_VERSION_ENV, DEFAULT_SERVICE_VERSION),
        environment=_read_string(env, ENVIRONMENT_ENV, DEFAULT_ENVIRONMENT),
        host=_read_string(env, HOST_ENV, DEFAULT_HOST),
        port=_read_port(env, PORT_ENV, DEFAULT_PORT),
        log_level=_read_string(env, LOG_LEVEL_ENV, DEFAULT_LOG_LEVEL),
        inference_device=_read_string(
            env,
            INFERENCE_DEVICE_ENV,
            DEFAULT_INFERENCE_DEVICE,
        ),
        internal_tokenized_endpoint_enabled=_read_bool(
            env,
            INTERNAL_TOKENIZED_ENDPOINT_ENABLED_ENV,
            DEFAULT_INTERNAL_TOKENIZED_ENDPOINT_ENABLED,
        ),
        pa_base_manifest_path=_read_optional_string(env, PA_BASE_MANIFEST_PATH_ENV),
        pa_micro_manifest_path=_read_optional_string(env, PA_MICRO_MANIFEST_PATH_ENV),
    )


def _read_string(env: Mapping[str, str], key: str, default: str) -> str:
    value = env.get(key)
    if value is None:
        return default
    return value


def _read_port(env: Mapping[str, str], key: str, default: int) -> int:
    value = env.get(key)
    if value is None:
        return default

    normalized_value = value.strip()
    if not normalized_value:
        raise ConfigurationError(f"{key} must not be empty.")

    try:
        return int(normalized_value)
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be an integer.") from exc


def _read_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    value = env.get(key)
    if value is None:
        return default

    normalized_value = value.strip().lower()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False

    raise ConfigurationError(f"{key} must be a boolean value.")


def _read_optional_string(env: Mapping[str, str], key: str) -> str | None:
    value = env.get(key)
    if value is None:
        return None
    return value


def _normalize_non_empty_string(field_name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ConfigurationError(f"{field_name} must be a string.")

    normalized_value = value.strip()
    if not normalized_value:
        raise ConfigurationError(f"{field_name} must not be empty.")

    return normalized_value


def _normalize_port(value: int) -> int:
    if not isinstance(value, int):
        raise ConfigurationError("port must be an integer.")

    if not 1 <= value <= 65535:
        raise ConfigurationError("port must be between 1 and 65535.")

    return value


def _normalize_choice(
    field_name: str,
    value: str,
    allowed_values: tuple[str, ...],
    *,
    normalize_to: Literal["lower", "upper"],
) -> str:
    normalized_value = _normalize_non_empty_string(field_name, value)
    if normalize_to == "lower":
        normalized_value = normalized_value.lower()
    else:
        normalized_value = normalized_value.upper()

    if normalized_value not in allowed_values:
        supported_values = ", ".join(allowed_values)
        raise ConfigurationError(
            f"{field_name} must be one of: {supported_values}."
        )

    return normalized_value


def _normalize_bool(field_name: str, value: bool) -> bool:
    if type(value) is not bool:
        raise ConfigurationError(f"{field_name} must be a boolean.")

    return value


def _normalize_optional_path(field_name: str, value: Path | str | None) -> Path | None:
    if value is None:
        return None

    if isinstance(value, bool):
        raise ConfigurationError(f"{field_name} must be a filesystem path.")

    if isinstance(value, str):
        normalized_value = value.strip()
        if not normalized_value:
            raise ConfigurationError(f"{field_name} must not be empty.")
        return Path(normalized_value)

    try:
        return Path(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{field_name} must be a filesystem path.") from exc
