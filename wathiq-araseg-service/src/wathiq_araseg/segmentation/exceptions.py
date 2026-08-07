"""Controlled exception hierarchy for internal segmentation abstractions."""


class SegmentationError(Exception):
    """Base exception for segmentation abstractions."""


class InvalidSegmentationInputError(SegmentationError):
    """Raised when a segmentation request is missing required input."""


class UnsupportedTrackError(SegmentationError):
    """Raised when no pipeline is available for a requested track."""


class PipelineRegistrationError(SegmentationError):
    """Raised when pipeline registration configuration is invalid."""


class DuplicatePipelineRegistrationError(PipelineRegistrationError):
    """Raised when more than one pipeline is registered for the same track."""


class InvalidSegmentationResultError(SegmentationError):
    """Raised when a concrete pipeline produces an invalid internal result."""


class InvalidTokenSequenceError(InvalidSegmentationInputError):
    """Raised when an internal token sequence is missing or malformed."""


class InvalidTokenIndexError(InvalidTokenSequenceError):
    """Raised when token indexes are invalid, duplicated, or non-sequential."""


class InvalidTokenSpanError(InvalidTokenSequenceError):
    """Raised when token spans are out of order, overlapping, or otherwise invalid."""


class TokenSourceSpanMismatchError(InvalidTokenSequenceError):
    """Raised when a token text does not match its exact source-text span."""


class TokenizedRequestNormalizationError(InvalidSegmentationInputError):
    """Raised when a tokenized request text is not already line-ending normalized."""


class InvalidBoundaryIndexError(InvalidSegmentationResultError):
    """Raised when token-boundary indexes are empty, invalid, or not strictly increasing."""


class MissingFinalBoundaryIndexError(InvalidBoundaryIndexError):
    """Raised when a boundary sequence does not terminate on the final token index."""


class SourceSegmentReconstructionError(InvalidSegmentationResultError):
    """Raised when exact source-text segment rendering fails to preserve the input."""
