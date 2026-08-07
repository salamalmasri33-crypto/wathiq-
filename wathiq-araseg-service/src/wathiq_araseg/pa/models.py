"""Immutable typed models for standalone PA probability inference."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import math

from .exceptions import InvalidOriginalTokenSequenceError, TokenCountMismatchError


@dataclass(frozen=True, slots=True)
class OriginalTokenSequence:
    """Ordered original-token sequence supplied to Milestone 5A inference."""

    tokens: tuple[str, ...]

    def __post_init__(self) -> None:
        raw_tokens = self.tokens
        if isinstance(raw_tokens, str):
            raise InvalidOriginalTokenSequenceError(
                "Original tokens must be supplied as an ordered token sequence."
            )

        if not isinstance(raw_tokens, Iterable):
            raise InvalidOriginalTokenSequenceError(
                "Original tokens must be supplied as an ordered token sequence."
            )

        tokens = tuple(raw_tokens)
        if not tokens:
            raise InvalidOriginalTokenSequenceError(
                "Original-token sequence must not be empty."
            )

        for token in tokens:
            if not isinstance(token, str):
                raise InvalidOriginalTokenSequenceError(
                    "Every original token must be a string."
                )
            if token == "":
                raise InvalidOriginalTokenSequenceError(
                    "Original tokens must not contain empty-string items."
                )

        object.__setattr__(self, "tokens", tokens)

    @property
    def token_count(self) -> int:
        """Return the number of original tokens."""

        return len(self.tokens)


@dataclass(frozen=True, slots=True)
class TokenProbability:
    """Aggregated base, micro, and blended probabilities for one original token."""

    token_index: int
    token: str
    base_probability: float
    micro_probability: float
    blended_probability: float
    base_observation_count: int
    micro_observation_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.token_index, int) or self.token_index < 0:
            raise TokenCountMismatchError("Token indexes must be non-negative integers.")

        if not isinstance(self.token, str) or self.token == "":
            raise TokenCountMismatchError("Token probability records must preserve token text.")

        for field_name in (
            "base_probability",
            "micro_probability",
            "blended_probability",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise TokenCountMismatchError("Token probabilities must be finite numbers.")
            if not 0.0 <= float(value) <= 1.0:
                raise TokenCountMismatchError("Token probabilities must remain within [0, 1].")

        for field_name in ("base_observation_count", "micro_observation_count"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 1:
                raise TokenCountMismatchError(
                    "Every token probability record must include a positive observation count."
                )


@dataclass(frozen=True, slots=True)
class PAProbabilityResult:
    """Final standalone Milestone 5A output for ordered token probabilities."""

    original_tokens: OriginalTokenSequence
    token_probabilities: tuple[TokenProbability, ...]
    window_count: int
    max_length: int
    stride: int
    base_weight: float
    micro_weight: float

    def __post_init__(self) -> None:
        if not isinstance(self.original_tokens, OriginalTokenSequence):
            raise TokenCountMismatchError(
                "Probability results must reference the original-token sequence."
            )

        token_probabilities = tuple(self.token_probabilities)
        if len(token_probabilities) != self.original_tokens.token_count:
            raise TokenCountMismatchError(
                "Probability results must contain exactly one record per original token."
            )

        for expected_index, (expected_token, token_probability) in enumerate(
            zip(self.original_tokens.tokens, token_probabilities, strict=True)
        ):
            if token_probability.token_index != expected_index:
                raise TokenCountMismatchError(
                    "Probability results must preserve original token indexes in order."
                )
            if token_probability.token != expected_token:
                raise TokenCountMismatchError(
                    "Probability results must preserve original token values in order."
                )

        object.__setattr__(self, "token_probabilities", token_probabilities)

        if not isinstance(self.window_count, int) or self.window_count < 1:
            raise TokenCountMismatchError("Probability results must record at least one window.")
        if not isinstance(self.max_length, int) or self.max_length < 1:
            raise TokenCountMismatchError("Probability results must record a valid max_length.")
        if not isinstance(self.stride, int) or self.stride < 1:
            raise TokenCountMismatchError("Probability results must record a valid stride.")
