"""Internal segmentation abstractions for the Wathiq AraSeg service."""

from .exceptions import (
    DuplicatePipelineRegistrationError,
    InvalidBoundaryIndexError,
    InvalidSegmentationInputError,
    InvalidSegmentationResultError,
    InvalidTokenIndexError,
    InvalidTokenSequenceError,
    InvalidTokenSpanError,
    MissingFinalBoundaryIndexError,
    PipelineRegistrationError,
    SegmentationError,
    SourceSegmentReconstructionError,
    TokenizedRequestNormalizationError,
    TokenSourceSpanMismatchError,
    UnsupportedTrackError,
)
from .fake_pipeline import FakeSegmentationPipeline
from .models import (
    SegmentationRequest,
    SegmentationResult,
    SegmentationSegment,
    SegmentationToken,
)
from .pipeline import AbstractSegmentationPipeline, render_segments_from_token_boundaries
from .raw_text_service import RawTextSegmentationService
from .registry import PipelineRegistry
from .service import SentenceSegmentationService
from .token_provider import LosslessUnicodeTokenSpanProvider, RawTextTokenSpanProvider

__all__ = [
    "AbstractSegmentationPipeline",
    "DuplicatePipelineRegistrationError",
    "FakeSegmentationPipeline",
    "InvalidBoundaryIndexError",
    "InvalidSegmentationInputError",
    "InvalidSegmentationResultError",
    "InvalidTokenIndexError",
    "InvalidTokenSequenceError",
    "InvalidTokenSpanError",
    "MissingFinalBoundaryIndexError",
    "PipelineRegistrationError",
    "render_segments_from_token_boundaries",
    "RawTextSegmentationService",
    "PipelineRegistry",
    "SegmentationError",
    "SegmentationRequest",
    "SegmentationResult",
    "SegmentationSegment",
    "SegmentationToken",
    "SourceSegmentReconstructionError",
    "SentenceSegmentationService",
    "LosslessUnicodeTokenSpanProvider",
    "RawTextTokenSpanProvider",
    "TokenizedRequestNormalizationError",
    "TokenSourceSpanMismatchError",
    "UnsupportedTrackError",
]
