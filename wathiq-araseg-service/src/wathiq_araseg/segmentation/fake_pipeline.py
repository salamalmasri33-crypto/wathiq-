"""Deterministic fake PA pipeline used to prove the segmentation abstraction."""

from __future__ import annotations

from collections.abc import Iterable

from .models import SegmentationRequest
from .pipeline import AbstractSegmentationPipeline


class FakeSegmentationPipeline(AbstractSegmentationPipeline):
    """Minimal fake PA strategy that returns the full input as one segment."""

    @property
    def track(self) -> str:
        return "PA"

    @property
    def pipeline_id(self) -> str:
        return "fake-pa-single-segment"

    def _run_pipeline(self, request: SegmentationRequest) -> Iterable[str]:
        return (request.text,)
