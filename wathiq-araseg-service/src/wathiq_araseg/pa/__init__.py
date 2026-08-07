"""Standalone PA probability inference components."""

from .alignment import TokenizerAlignment, TokenizerWindow, build_first_subtoken_alignment
from .exceptions import (
    InvalidInferenceDependencyError,
    InvalidOriginalTokenSequenceError,
    InvalidWordIdError,
    MissingTokenObservationError,
    NonFiniteModelOutputError,
    PAInferenceError,
    ProbabilityShapeMismatchError,
    TokenCountMismatchError,
    TokenizerModelCompatibilityError,
    UnsupportedTokenizerBehaviorError,
)
from .models import OriginalTokenSequence, PAProbabilityResult, TokenProbability
from .pipeline import PAPipeline
from .window_inference import (
    PA_BASE_WEIGHT,
    PA_BOUNDARY_CLASS_ID,
    PA_MAX_LENGTH,
    PA_MICRO_WEIGHT,
    PA_STRIDE,
    PAEnsembleWindowInferenceEngine,
)

__all__ = [
    "InvalidInferenceDependencyError",
    "InvalidOriginalTokenSequenceError",
    "InvalidWordIdError",
    "MissingTokenObservationError",
    "NonFiniteModelOutputError",
    "OriginalTokenSequence",
    "PAInferenceError",
    "PAProbabilityResult",
    "PA_BASE_WEIGHT",
    "PA_BOUNDARY_CLASS_ID",
    "PA_MAX_LENGTH",
    "PA_MICRO_WEIGHT",
    "PAPipeline",
    "PA_STRIDE",
    "PAEnsembleWindowInferenceEngine",
    "ProbabilityShapeMismatchError",
    "TokenCountMismatchError",
    "TokenProbability",
    "TokenizerAlignment",
    "TokenizerModelCompatibilityError",
    "TokenizerWindow",
    "UnsupportedTokenizerBehaviorError",
    "build_first_subtoken_alignment",
]
