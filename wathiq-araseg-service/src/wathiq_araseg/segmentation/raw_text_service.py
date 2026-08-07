"""Raw-text orchestration over token-span providers and segmentation pipelines."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .exceptions import InvalidSegmentationInputError, PipelineRegistrationError
from .models import SegmentationRequest, SegmentationResult, SegmentationToken
from .pipeline import AbstractSegmentationPipeline
from .token_provider import RawTextTokenSpanProvider


@dataclass(frozen=True, slots=True)
class RawTextSegmentationOutcome:
    """Successful raw-text segmentation outcome with the exact produced tokens."""

    tokens: tuple[SegmentationToken, ...]
    result: SegmentationResult


class RawTextSegmentationService:
    """Convert raw text to token spans and delegate segmentation to one pipeline."""

    def __init__(
        self,
        token_span_provider: RawTextTokenSpanProvider,
        segmentation_pipeline: AbstractSegmentationPipeline,
    ) -> None:
        if not isinstance(token_span_provider, RawTextTokenSpanProvider):
            raise PipelineRegistrationError(
                "RawTextSegmentationService requires a RawTextTokenSpanProvider dependency."
            )
        if not isinstance(segmentation_pipeline, AbstractSegmentationPipeline):
            raise PipelineRegistrationError(
                "RawTextSegmentationService requires an AbstractSegmentationPipeline dependency."
            )

        self._token_span_provider = token_span_provider
        self._segmentation_pipeline = segmentation_pipeline

    def segment(self, request: SegmentationRequest) -> SegmentationResult:
        return self.segment_with_tokens(request).result

    def segment_with_tokens(
        self,
        request: SegmentationRequest,
    ) -> RawTextSegmentationOutcome:
        if not isinstance(request, SegmentationRequest):
            raise InvalidSegmentationInputError(
                "Raw-text segmentation requires a SegmentationRequest."
            )
        if request.tokens is not None:
            raise InvalidSegmentationInputError(
                "Raw-text segmentation requests must not provide precomputed tokens."
            )

        produced_tokens = self._token_span_provider.provide(request.text)
        tokenized_request = replace(request, tokens=produced_tokens)
        tokenized_request_tokens = tokenized_request.tokens
        if tokenized_request_tokens is None:
            raise InvalidSegmentationInputError(
                "Raw-text segmentation requires the token provider to return an exact token tuple."
            )

        result = self._segmentation_pipeline.segment(tokenized_request)
        return RawTextSegmentationOutcome(
            tokens=tokenized_request_tokens,
            result=result,
        )
