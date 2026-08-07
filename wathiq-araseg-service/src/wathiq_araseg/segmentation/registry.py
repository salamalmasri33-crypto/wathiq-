"""Explicit pipeline registry for internal track resolution."""

from __future__ import annotations

from collections.abc import Iterable

from .exceptions import (
    DuplicatePipelineRegistrationError,
    PipelineRegistrationError,
    UnsupportedTrackError,
)
from .pipeline import AbstractSegmentationPipeline


class PipelineRegistry:
    """Registers and resolves pipeline instances by explicit track."""

    def __init__(self, pipelines: Iterable[AbstractSegmentationPipeline] | None = None) -> None:
        self._pipelines: dict[str, AbstractSegmentationPipeline] = {}

        for pipeline in pipelines or ():
            self.register(pipeline)

    def register(self, pipeline: AbstractSegmentationPipeline) -> None:
        if not isinstance(pipeline, AbstractSegmentationPipeline):
            raise PipelineRegistrationError(
                "Pipeline registry accepts only AbstractSegmentationPipeline instances."
            )

        track = _normalize_track(pipeline.track)
        if track in self._pipelines:
            raise DuplicatePipelineRegistrationError(
                f"A segmentation pipeline is already registered for track '{track}'."
            )

        self._pipelines[track] = pipeline

    def resolve(self, track: str) -> AbstractSegmentationPipeline:
        normalized_track = _normalize_track(track)

        try:
            return self._pipelines[normalized_track]
        except KeyError as exc:
            raise UnsupportedTrackError(
                f"Unsupported segmentation track '{normalized_track}'."
            ) from exc


def _normalize_track(track: str) -> str:
    if not isinstance(track, str) or not track.strip():
        raise UnsupportedTrackError("Segmentation track must be a non-empty string.")

    return track.strip().upper()
