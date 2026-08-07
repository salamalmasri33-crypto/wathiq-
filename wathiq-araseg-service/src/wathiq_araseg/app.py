"""FastAPI application factory for the Wathiq AraSeg service."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from wathiq_araseg.api import (
    health_router,
    internal_segmentation_router,
    segmentation_router,
)
from wathiq_araseg.api.errors import register_error_handlers
from wathiq_araseg.config import ServiceConfig, load_service_config
from wathiq_araseg.logging_config import configure_logging
from wathiq_araseg.runtime import PARuntimeBuilderError, build_pa_pipeline
from wathiq_araseg.segmentation import (
    FakeSegmentationPipeline,
    LosslessUnicodeTokenSpanProvider,
    PipelineRegistry,
    PipelineRegistrationError,
    RawTextSegmentationService,
    SentenceSegmentationService,
)

logger = logging.getLogger("wathiq_araseg.app")


class ApplicationStartupError(RuntimeError):
    """Raised when the internal real PA dependencies cannot be composed safely."""


def create_app(settings: ServiceConfig | None = None) -> FastAPI:
    """Create the FastAPI application without loading the PA model."""

    app_settings = settings if settings is not None else load_service_config()
    configure_logging(app_settings.log_level)
    segmentation_service = _build_segmentation_service()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        internal_pa_pipeline = None
        internal_pa_token_span_provider = None
        internal_pa_raw_text_service = None
        if app_settings.internal_tokenized_endpoint_enabled:
            internal_pa_pipeline = _build_internal_pa_pipeline(app_settings)
            internal_pa_token_span_provider = _build_internal_pa_token_span_provider()
            internal_pa_raw_text_service = _build_internal_pa_raw_text_service(
                token_span_provider=internal_pa_token_span_provider,
                segmentation_pipeline=internal_pa_pipeline,
            )

        app.state.settings = app_settings
        app.state.segmentation_service = segmentation_service
        app.state.internal_pa_pipeline = internal_pa_pipeline
        app.state.internal_pa_token_span_provider = internal_pa_token_span_provider
        app.state.internal_pa_raw_text_service = internal_pa_raw_text_service
        logger.info(
            "Application startup complete.",
            extra={
                "event": "application.startup",
                "service": app_settings.service_name,
                "version": app_settings.service_version,
                "environment": app_settings.environment,
                "device": app_settings.inference_device,
                "modelReady": internal_pa_pipeline is not None,
            },
        )
        try:
            yield
        finally:
            logger.info(
                "Application shutdown complete.",
                extra={
                    "event": "application.shutdown",
                    "service": app_settings.service_name,
                    "version": app_settings.service_version,
                    "environment": app_settings.environment,
                    "device": app_settings.inference_device,
                    "modelReady": internal_pa_pipeline is not None,
                },
            )

    application = FastAPI(
        title=app_settings.service_name,
        version=app_settings.service_version,
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.segmentation_service = segmentation_service
    application.state.internal_pa_pipeline = None
    application.state.internal_pa_token_span_provider = None
    application.state.internal_pa_raw_text_service = None
    register_error_handlers(application)
    application.include_router(health_router)
    application.include_router(segmentation_router)
    if app_settings.internal_tokenized_endpoint_enabled:
        application.include_router(internal_segmentation_router)

    return application


def _build_segmentation_service() -> SentenceSegmentationService:
    fake_pa_pipeline = FakeSegmentationPipeline()
    pipeline_registry = PipelineRegistry([fake_pa_pipeline])

    return SentenceSegmentationService(pipeline_registry)


def _build_internal_pa_pipeline(settings: ServiceConfig):
    if settings.pa_base_manifest_path is None or settings.pa_micro_manifest_path is None:
        raise ApplicationStartupError(
            "The internal PA endpoints require explicit base and micro manifest paths."
        )

    try:
        return build_pa_pipeline(
            settings.pa_base_manifest_path,
            settings.pa_micro_manifest_path,
            device="cpu",
        )
    except PARuntimeBuilderError as exc:
        raise ApplicationStartupError(
            "Unable to compose the internal PA pipeline at startup."
        ) from exc


def _build_internal_pa_token_span_provider() -> LosslessUnicodeTokenSpanProvider:
    return LosslessUnicodeTokenSpanProvider()


def _build_internal_pa_raw_text_service(
    *,
    token_span_provider: LosslessUnicodeTokenSpanProvider,
    segmentation_pipeline,
) -> RawTextSegmentationService:
    try:
        return RawTextSegmentationService(
            token_span_provider=token_span_provider,
            segmentation_pipeline=segmentation_pipeline,
        )
    except PipelineRegistrationError as exc:
        raise ApplicationStartupError(
            "Unable to compose the internal raw-text PA segmentation service at startup."
        ) from exc
