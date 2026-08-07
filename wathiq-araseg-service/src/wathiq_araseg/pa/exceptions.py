"""Controlled exceptions for standalone PA window inference."""


class PAInferenceError(Exception):
    """Base exception for standalone PA probability inference."""


class InvalidInferenceDependencyError(PAInferenceError):
    """Raised when PAPipeline receives an invalid inference-engine dependency."""


class InvalidOriginalTokenSequenceError(PAInferenceError):
    """Raised when the supplied original-token sequence is invalid."""


class UnsupportedTokenizerBehaviorError(PAInferenceError):
    """Raised when the tokenizer cannot provide the required fast alignment behavior."""


class InvalidWordIdError(PAInferenceError):
    """Raised when tokenizer word IDs do not map safely to the original-token sequence."""


class MissingTokenObservationError(PAInferenceError):
    """Raised when one or more original tokens receive no probability observations."""


class TokenCountMismatchError(PAInferenceError):
    """Raised when token counts or token order diverge during aggregation."""


class TokenizerModelCompatibilityError(PAInferenceError):
    """Raised when the tokenizer and loaded models are not mutually compatible."""


class NonFiniteModelOutputError(PAInferenceError):
    """Raised when model logits or probabilities contain NaN or infinite values."""


class ProbabilityShapeMismatchError(PAInferenceError):
    """Raised when model outputs do not match the required token-classification shape."""


class InvalidPAProbabilityResultError(PAInferenceError):
    """Raised when the supplied PA probability result is invalid for post-processing."""


class TokenIndexMismatchError(PAInferenceError):
    """Raised when a token record index diverges from the original-token sequence."""


class TokenTextMismatchError(PAInferenceError):
    """Raised when a token record text diverges from the original-token sequence."""


class InvalidProbabilityValueError(PAInferenceError):
    """Raised when a post-processing probability is non-finite or out of range."""


class InvalidThresholdConfigurationError(PAInferenceError):
    """Raised when fixed PA threshold constants are invalid."""


class InvalidPunctuationConfigurationError(PAInferenceError):
    """Raised when fixed PA punctuation configuration is invalid."""


class InvalidParagraphMarkerConfigurationError(PAInferenceError):
    """Raised when fixed PA paragraph-marker configuration is invalid."""


class MissingFinalBoundaryError(PAInferenceError):
    """Raised when post-processing fails to terminate the final original token."""


class DecisionCoverageMismatchError(PAInferenceError):
    """Raised when token-boundary decisions do not cover the original tokens exactly once."""


class SentenceGroupCoverageMismatchError(PAInferenceError):
    """Raised when sentence groups do not cover the original tokens exactly once."""
