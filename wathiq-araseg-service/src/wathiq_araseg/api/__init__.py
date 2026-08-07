"""API routes for the Wathiq AraSeg service."""

from .health import router as health_router
from .segmentation import (
    internal_router as internal_segmentation_router,
    router as segmentation_router,
)

__all__ = ["health_router", "internal_segmentation_router", "segmentation_router"]
