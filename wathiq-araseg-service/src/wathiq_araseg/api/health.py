"""Health endpoint for the Wathiq AraSeg service."""

from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Request
from pydantic import BaseModel

from wathiq_araseg.config import ServiceConfig

router = APIRouter()


class HealthResponse(BaseModel):
    """Stable Milestone 2 health response."""

    status: Literal["healthy"]
    service: str
    version: str
    modelReady: bool
    device: str


@router.get("/health", response_model=HealthResponse, tags=["health"])
def get_health(request: Request) -> HealthResponse:
    """Return static service readiness without loading the model."""

    settings = cast(ServiceConfig, request.app.state.settings)

    return HealthResponse(
        status="healthy",
        service=settings.service_name,
        version=settings.service_version,
        modelReady=False,
        device=settings.inference_device,
    )
