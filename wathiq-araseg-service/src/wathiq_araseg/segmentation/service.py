"""Application service that delegates segmentation through the registry."""

from __future__ import annotations

from .exceptions import PipelineRegistrationError
from .models import SegmentationRequest, SegmentationResult
from .registry import PipelineRegistry


class SentenceSegmentationService:
    """Thin application service over the pipeline registry abstraction."""

    def __init__(self, pipeline_registry: PipelineRegistry) -> None:
        if not isinstance(pipeline_registry, PipelineRegistry):
            raise PipelineRegistrationError(
                "SentenceSegmentationService requires a PipelineRegistry instance."
            )

        self._pipeline_registry = pipeline_registry

    def segment(self, request: SegmentationRequest) -> SegmentationResult:
        pipeline = self._pipeline_registry.resolve(request.track)
        return pipeline.segment(request)
