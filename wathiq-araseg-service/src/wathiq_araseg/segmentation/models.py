"""Internal typed models for segmentation abstractions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .exceptions import (
    InvalidTokenIndexError,
    InvalidTokenSequenceError,
    InvalidTokenSpanError,
    TokenSourceSpanMismatchError,
)


@dataclass(frozen=True, slots=True)
class SegmentationToken:
    """Exact original token with a validated source-text span."""

    index: int
    text: str
    start_offset: int
    end_offset: int

    def __post_init__(self) -> None:
        if not _is_real_int(self.index) or self.index < 0:
            raise InvalidTokenIndexError(
                "Segmentation token indexes must be non-negative integers."
            )

        if not isinstance(self.text, str) or self.text == "":
            raise InvalidTokenSequenceError(
                "Segmentation tokens must preserve non-empty string values."
            )

        if not _is_real_int(self.start_offset) or self.start_offset < 0:
            raise InvalidTokenSpanError(
                "Segmentation token start offsets must be non-negative integers."
            )

        if not _is_real_int(self.end_offset) or self.end_offset <= self.start_offset:
            raise InvalidTokenSpanError(
                "Segmentation token end offsets must be integers greater than start offsets."
            )


@dataclass(frozen=True, slots=True)
class SegmentationRequest:
    """Internal request passed through the segmentation abstraction."""

    document_id: str
    text: str
    track: str
    tokens: tuple[SegmentationToken, ...] | None = None

    def __post_init__(self) -> None:
        if self.tokens is None:
            return

        if not isinstance(self.text, str):
            raise InvalidTokenSequenceError(
                "Tokenized segmentation requests require a string source text."
            )

        object.__setattr__(
            self,
            "tokens",
            _coerce_segmentation_tokens(self.text, self.tokens),
        )


@dataclass(frozen=True, slots=True)
class SegmentationSegment:
    """Ordered internal segment produced by a segmentation pipeline."""

    index: int
    text: str


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    """Internal segmentation result returned by the application service."""

    document_id: str
    track: str
    pipeline_id: str
    normalized_text: str
    segments: tuple[SegmentationSegment, ...]


def _coerce_segmentation_tokens(
    source_text: str,
    tokens: Iterable[SegmentationToken],
) -> tuple[SegmentationToken, ...]:
    if isinstance(tokens, (str, bytes)):
        raise InvalidTokenSequenceError(
            "Segmentation tokens must be supplied as an ordered token collection."
        )

    if not isinstance(tokens, Iterable):
        raise InvalidTokenSequenceError(
            "Segmentation tokens must be supplied as an ordered token collection."
        )

    token_tuple = tuple(tokens)
    if not token_tuple:
        raise InvalidTokenSequenceError(
            "Tokenized segmentation requests must include at least one token."
        )

    previous_end_offset: int | None = None
    source_length = len(source_text)

    for expected_index, token in enumerate(token_tuple):
        if not isinstance(token, SegmentationToken):
            raise InvalidTokenSequenceError(
                "Segmentation tokens must use the controlled SegmentationToken type."
            )

        if token.index != expected_index:
            raise InvalidTokenIndexError(
                "Segmentation token indexes must be sequential from 0 without gaps."
            )

        if token.end_offset > source_length:
            raise InvalidTokenSpanError(
                "Segmentation token spans must remain within the source-text bounds."
            )

        if previous_end_offset is not None and token.start_offset < previous_end_offset:
            raise InvalidTokenSpanError(
                "Segmentation token spans must be ordered and non-overlapping."
            )

        source_slice = source_text[token.start_offset : token.end_offset]
        if source_slice != token.text:
            raise TokenSourceSpanMismatchError(
                "Segmentation token text must match its exact source-text span."
            )

        previous_end_offset = token.end_offset

    return token_tuple


def _is_real_int(value: object) -> bool:
    return type(value) is int
