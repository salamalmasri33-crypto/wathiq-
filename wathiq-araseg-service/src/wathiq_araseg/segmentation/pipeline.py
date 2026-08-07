"""Abstract segmentation pipeline using a small Template Method lifecycle."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import replace

from .exceptions import (
    InvalidBoundaryIndexError,
    InvalidSegmentationInputError,
    InvalidSegmentationResultError,
    InvalidTokenSequenceError,
    MissingFinalBoundaryIndexError,
    SourceSegmentReconstructionError,
    TokenizedRequestNormalizationError,
)
from .models import (
    SegmentationRequest,
    SegmentationResult,
    SegmentationSegment,
    SegmentationToken,
    _coerce_segmentation_tokens,
)


class AbstractSegmentationPipeline(ABC):
    """Common lifecycle for internal segmentation pipelines."""

    @property
    @abstractmethod
    def track(self) -> str:
        """Return the explicit track handled by this pipeline."""

    @property
    @abstractmethod
    def pipeline_id(self) -> str:
        """Return a stable internal identifier for this pipeline."""

    def segment(self, request: SegmentationRequest) -> SegmentationResult:
        """Validate, normalize, execute, and validate a segmentation request."""

        validated_request = self._validate_request(request)
        normalized_request = self._normalize_request(validated_request)

        try:
            raw_segments = tuple(self._run_pipeline(normalized_request))
        except InvalidSegmentationResultError:
            raise
        except Exception as exc:
            raise InvalidSegmentationResultError(
                f"Pipeline '{self.pipeline_id}' failed to produce a valid internal result."
            ) from exc

        result = SegmentationResult(
            document_id=normalized_request.document_id,
            track=self.track,
            pipeline_id=self.pipeline_id,
            normalized_text=normalized_request.text,
            segments=self._build_segments(raw_segments),
        )
        self._validate_result(normalized_request, result)

        return result

    @abstractmethod
    def _run_pipeline(self, request: SegmentationRequest) -> Iterable[str]:
        """Execute concrete pipeline logic against a normalized request."""

    def _validate_request(self, request: SegmentationRequest) -> SegmentationRequest:
        if not isinstance(request, SegmentationRequest):
            raise InvalidSegmentationInputError(
                "Segmentation request must be a SegmentationRequest instance."
            )

        if not isinstance(request.document_id, str) or not request.document_id.strip():
            raise InvalidSegmentationInputError("Document identifier must not be blank.")

        if not isinstance(request.text, str) or not request.text.strip():
            raise InvalidSegmentationInputError("Segmentation text must not be blank.")

        if not isinstance(request.track, str) or not request.track.strip():
            raise InvalidSegmentationInputError("Segmentation track must not be blank.")

        if request.tokens is not None:
            normalized_text = _normalize_line_endings(request.text)
            if normalized_text != request.text:
                raise TokenizedRequestNormalizationError(
                    "Tokenized segmentation requests must already use normalized line endings."
                )

            validated_tokens = _coerce_segmentation_tokens(request.text, request.tokens)
            request = replace(request, tokens=validated_tokens)

        return request

    def _normalize_request(self, request: SegmentationRequest) -> SegmentationRequest:
        normalized_text = _normalize_line_endings(request.text)

        return replace(
            request,
            document_id=request.document_id.strip(),
            text=normalized_text,
            track=request.track.strip().upper(),
        )

    def _build_segments(self, raw_segments: tuple[str, ...]) -> tuple[SegmentationSegment, ...]:
        segments: list[SegmentationSegment] = []

        for index, segment_text in enumerate(raw_segments):
            if not isinstance(segment_text, str):
                raise InvalidSegmentationResultError(
                    "Concrete pipelines must return string segment values."
                )

            if segment_text == "":
                raise InvalidSegmentationResultError(
                    "Concrete pipelines must not return empty segments."
                )

            segments.append(SegmentationSegment(index=index, text=segment_text))

        return tuple(segments)

    def _validate_result(
        self,
        request: SegmentationRequest,
        result: SegmentationResult,
    ) -> None:
        if not result.pipeline_id.strip():
            raise InvalidSegmentationResultError("Pipeline identifier must not be blank.")

        if result.track != self.track:
            raise InvalidSegmentationResultError(
                "Pipeline result track must match the concrete pipeline track."
            )

        if result.document_id != request.document_id:
            raise InvalidSegmentationResultError(
                "Pipeline result document identifier must match the normalized request."
            )

        if result.normalized_text != request.text:
            raise InvalidSegmentationResultError(
                "Pipeline result text must match the normalized request text."
            )

        if not result.segments:
            raise InvalidSegmentationResultError(
                "Pipeline result must contain at least one ordered segment."
            )

        reconstructed_text = "".join(segment.text for segment in result.segments)
        if reconstructed_text != request.text:
            raise InvalidSegmentationResultError(
                "Pipeline result segments must preserve the complete normalized input."
            )


def render_segments_from_token_boundaries(
    normalized_text: str,
    tokens: tuple[SegmentationToken, ...],
    boundary_token_indices: tuple[int, ...],
) -> tuple[str, ...]:
    """Render exact source-text segments from validated token spans and boundary indexes."""

    if not isinstance(normalized_text, str):
        raise SourceSegmentReconstructionError(
            "Exact source-text rendering requires a normalized source string."
        )

    validated_tokens = _coerce_segmentation_tokens(normalized_text, tokens)
    validated_boundaries = _coerce_boundary_token_indices(
        validated_tokens,
        boundary_token_indices,
    )

    segments: list[str] = []
    source_cursor = 0
    final_boundary_position = len(validated_boundaries) - 1

    for boundary_position, boundary_token_index in enumerate(validated_boundaries):
        boundary_token = validated_tokens[boundary_token_index]
        segment_end = (
            len(normalized_text)
            if boundary_position == final_boundary_position
            else boundary_token.end_offset
        )

        if segment_end < source_cursor:
            raise SourceSegmentReconstructionError(
                "Exact source-text segments must advance monotonically through the source."
            )

        segment_text = normalized_text[source_cursor:segment_end]
        if segment_text == "":
            raise SourceSegmentReconstructionError(
                "Exact source-text rendering must not create empty segments."
            )

        segments.append(segment_text)
        source_cursor = segment_end

    rendered_segments = tuple(segments)
    if "".join(rendered_segments) != normalized_text:
        raise SourceSegmentReconstructionError(
            "Exact source-text rendering must preserve the complete normalized input."
        )

    return rendered_segments


def _coerce_boundary_token_indices(
    tokens: tuple[SegmentationToken, ...],
    boundary_token_indices: tuple[int, ...],
) -> tuple[int, ...]:
    if isinstance(boundary_token_indices, (str, bytes)):
        raise InvalidBoundaryIndexError(
            "Boundary token indexes must be supplied as an ordered integer collection."
        )

    if not isinstance(boundary_token_indices, Iterable):
        raise InvalidBoundaryIndexError(
            "Boundary token indexes must be supplied as an ordered integer collection."
        )

    boundary_tuple = tuple(boundary_token_indices)
    if not boundary_tuple:
        raise InvalidBoundaryIndexError(
            "Boundary token indexes must contain at least one final boundary."
        )

    previous_boundary: int | None = None
    final_token_index = len(tokens) - 1

    for boundary_index in boundary_tuple:
        if type(boundary_index) is not int:
            raise InvalidBoundaryIndexError(
                "Boundary token indexes must be real integers."
            )

        if boundary_index < 0 or boundary_index > final_token_index:
            raise InvalidBoundaryIndexError(
                "Boundary token indexes must remain within token bounds."
            )

        if previous_boundary is not None and boundary_index <= previous_boundary:
            raise InvalidBoundaryIndexError(
                "Boundary token indexes must be strictly increasing without duplicates."
            )

        previous_boundary = boundary_index

    if boundary_tuple[-1] != final_token_index:
        raise MissingFinalBoundaryIndexError(
            "Boundary token indexes must terminate on the final token index."
        )

    return boundary_tuple


def _normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")
