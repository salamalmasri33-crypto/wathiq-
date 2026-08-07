"""Exact recovered PA boundary post-processing and token grouping."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from .exceptions import (
    DecisionCoverageMismatchError,
    InvalidPAProbabilityResultError,
    InvalidParagraphMarkerConfigurationError,
    InvalidProbabilityValueError,
    InvalidPunctuationConfigurationError,
    InvalidThresholdConfigurationError,
    MissingFinalBoundaryError,
    SentenceGroupCoverageMismatchError,
    TokenCountMismatchError,
    TokenIndexMismatchError,
    TokenTextMismatchError,
)
from .models import OriginalTokenSequence, PAProbabilityResult, TokenProbability

DEFAULT_THRESHOLD = 0.543
PUNCTUATION_THRESHOLD = 0.310
PUNCTUATION_TOKENS = (
    ".",
    "؟",
    "?",
    "!",
    "…",
)
PARAGRAPH_MARKERS = (
    "\\n",
    "\n",
    "[PAR]",
)
_FLOAT_TOLERANCE = 1e-12


class BoundaryDecisionReason(str, Enum):
    """Controlled semantic reasons for the effective final PA boundary decision."""

    DEFAULT_THRESHOLD = "default_threshold"
    PUNCTUATION_THRESHOLD = "punctuation_threshold"
    PARAGRAPH_MARKER = "paragraph_marker"
    BEFORE_PARAGRAPH = "before_paragraph"
    FORCE_LAST = "force_last"


@dataclass(frozen=True, slots=True)
class TokenBoundaryDecision:
    """Final token-level boundary decision after recovered PA post-processing."""

    token_index: int
    token: str
    probability: float
    applied_threshold: float
    is_boundary: bool
    decision_reason: BoundaryDecisionReason

    def __post_init__(self) -> None:
        if not isinstance(self.token_index, int) or self.token_index < 0:
            raise TokenIndexMismatchError("Token-boundary decisions require non-negative indexes.")
        if not isinstance(self.token, str) or self.token == "":
            raise TokenTextMismatchError("Token-boundary decisions must preserve token text.")
        if not isinstance(self.is_boundary, bool):
            raise InvalidPAProbabilityResultError(
                "Token-boundary decisions must store a real bool boundary flag."
            )
        if not isinstance(self.decision_reason, BoundaryDecisionReason):
            raise InvalidPAProbabilityResultError(
                "Token-boundary decisions must use a controlled decision reason."
            )

        probability = _validate_unit_interval(
            self.probability,
            exception_type=InvalidProbabilityValueError,
            message="Token-boundary decisions require finite probabilities within [0, 1].",
        )
        threshold = _validate_unit_interval(
            self.applied_threshold,
            exception_type=InvalidThresholdConfigurationError,
            message="Token-boundary decisions require finite thresholds within [0, 1].",
        )

        object.__setattr__(self, "probability", probability)
        object.__setattr__(self, "applied_threshold", threshold)


@dataclass(frozen=True, slots=True)
class SentenceTokenGroup:
    """Ordered token group terminated by one final PA boundary decision."""

    sentence_index: int
    start_token_index: int
    end_token_index: int
    tokens: tuple[str, ...]
    boundary_token_index: int
    boundary_reason: BoundaryDecisionReason

    def __post_init__(self) -> None:
        if not isinstance(self.sentence_index, int) or self.sentence_index < 0:
            raise SentenceGroupCoverageMismatchError(
                "Sentence groups require non-negative sentence indexes."
            )
        if not isinstance(self.start_token_index, int) or self.start_token_index < 0:
            raise SentenceGroupCoverageMismatchError(
                "Sentence groups require non-negative start indexes."
            )
        if not isinstance(self.end_token_index, int) or self.end_token_index < self.start_token_index:
            raise SentenceGroupCoverageMismatchError(
                "Sentence groups require an end index at or after the start index."
            )
        if self.boundary_token_index != self.end_token_index:
            raise SentenceGroupCoverageMismatchError(
                "Sentence groups must terminate at their boundary token index."
            )
        if not isinstance(self.boundary_reason, BoundaryDecisionReason):
            raise SentenceGroupCoverageMismatchError(
                "Sentence groups must record a controlled boundary reason."
            )

        tokens = tuple(self.tokens)
        if not tokens:
            raise SentenceGroupCoverageMismatchError("Sentence groups must not be empty.")
        if any(not isinstance(token, str) or token == "" for token in tokens):
            raise SentenceGroupCoverageMismatchError(
                "Sentence groups must preserve non-empty token strings."
            )
        expected_length = self.end_token_index - self.start_token_index + 1
        if len(tokens) != expected_length:
            raise SentenceGroupCoverageMismatchError(
                "Sentence-group token count must match the inclusive index span."
            )

        object.__setattr__(self, "tokens", tokens)


@dataclass(frozen=True, slots=True)
class PAPostProcessingResult:
    """Final deterministic PA post-processing output."""

    original_tokens: tuple[str, ...]
    decisions: tuple[TokenBoundaryDecision, ...]
    sentence_groups: tuple[SentenceTokenGroup, ...]
    default_threshold: float
    punctuation_threshold: float
    punctuation_tokens: tuple[str, ...]
    paragraph_markers: tuple[str, ...]
    paragraph_rule_enabled: bool
    force_last_enabled: bool

    def __post_init__(self) -> None:
        original_tokens = tuple(self.original_tokens)
        if not original_tokens:
            raise InvalidPAProbabilityResultError(
                "Post-processing results must preserve a non-empty original-token sequence."
            )
        if any(not isinstance(token, str) or token == "" for token in original_tokens):
            raise InvalidPAProbabilityResultError(
                "Post-processing results must preserve non-empty token strings."
            )
        object.__setattr__(self, "original_tokens", original_tokens)

        decisions = tuple(self.decisions)
        if len(decisions) != len(original_tokens):
            raise DecisionCoverageMismatchError(
                "Post-processing decisions must contain exactly one record per original token."
            )

        boundary_indexes: list[int] = []
        for expected_index, (expected_token, decision) in enumerate(
            zip(original_tokens, decisions, strict=True)
        ):
            if not isinstance(decision, TokenBoundaryDecision):
                raise DecisionCoverageMismatchError(
                    "Post-processing decisions must be token-boundary decision records."
                )
            if decision.token_index != expected_index:
                raise TokenIndexMismatchError(
                    "Post-processing decisions must preserve exact token indexes in order."
                )
            if decision.token != expected_token:
                raise TokenTextMismatchError(
                    "Post-processing decisions must preserve exact token values in order."
                )
            if decision.is_boundary:
                boundary_indexes.append(expected_index)

        object.__setattr__(self, "decisions", decisions)

        if not decisions[-1].is_boundary:
            raise MissingFinalBoundaryError(
                "The final post-processing decision must terminate the final original token."
            )

        default_threshold = _validate_unit_interval(
            self.default_threshold,
            exception_type=InvalidThresholdConfigurationError,
            message="Post-processing results must expose a valid default threshold.",
        )
        punctuation_threshold = _validate_unit_interval(
            self.punctuation_threshold,
            exception_type=InvalidThresholdConfigurationError,
            message="Post-processing results must expose a valid punctuation threshold.",
        )
        object.__setattr__(self, "default_threshold", default_threshold)
        object.__setattr__(self, "punctuation_threshold", punctuation_threshold)

        punctuation_tokens = tuple(self.punctuation_tokens)
        if any(not isinstance(token, str) or token == "" for token in punctuation_tokens):
            raise InvalidPunctuationConfigurationError(
                "Post-processing results must preserve non-empty punctuation tokens."
            )
        object.__setattr__(self, "punctuation_tokens", punctuation_tokens)

        paragraph_markers = tuple(self.paragraph_markers)
        if any(not isinstance(token, str) or token == "" for token in paragraph_markers):
            raise InvalidParagraphMarkerConfigurationError(
                "Post-processing results must preserve non-empty paragraph markers."
            )
        object.__setattr__(self, "paragraph_markers", paragraph_markers)

        if not isinstance(self.paragraph_rule_enabled, bool):
            raise InvalidPAProbabilityResultError(
                "Post-processing results must record a real bool for paragraph_rule_enabled."
            )
        if not isinstance(self.force_last_enabled, bool):
            raise InvalidPAProbabilityResultError(
                "Post-processing results must record a real bool for force_last_enabled."
            )

        sentence_groups = tuple(self.sentence_groups)
        if not sentence_groups:
            raise SentenceGroupCoverageMismatchError(
                "Post-processing results must preserve at least one sentence group."
            )

        expected_next_start = 0
        group_end_indexes: list[int] = []
        for expected_sentence_index, group in enumerate(sentence_groups):
            if not isinstance(group, SentenceTokenGroup):
                raise SentenceGroupCoverageMismatchError(
                    "Sentence groups must use the controlled immutable sentence-group type."
                )
            if group.sentence_index != expected_sentence_index:
                raise SentenceGroupCoverageMismatchError(
                    "Sentence indexes must start at 0 and remain sequential."
                )
            if group.start_token_index != expected_next_start:
                raise SentenceGroupCoverageMismatchError(
                    "Sentence groups must cover original tokens in one ordered contiguous pass."
                )
            if group.end_token_index >= len(original_tokens):
                raise SentenceGroupCoverageMismatchError(
                    "Sentence groups must remain within original-token bounds."
                )
            expected_tokens = original_tokens[group.start_token_index : group.end_token_index + 1]
            if group.tokens != expected_tokens:
                raise SentenceGroupCoverageMismatchError(
                    "Sentence groups must preserve the exact original token values."
                )
            terminating_decision = decisions[group.end_token_index]
            if not terminating_decision.is_boundary:
                raise SentenceGroupCoverageMismatchError(
                    "Every sentence group must terminate on a final boundary decision."
                )
            if group.boundary_reason is not terminating_decision.decision_reason:
                raise SentenceGroupCoverageMismatchError(
                    "Sentence groups must reuse the terminating decision reason."
                )

            group_end_indexes.append(group.end_token_index)
            expected_next_start = group.end_token_index + 1

        object.__setattr__(self, "sentence_groups", sentence_groups)

        if expected_next_start != len(original_tokens):
            raise SentenceGroupCoverageMismatchError(
                "Sentence groups must cover every original token exactly once."
            )
        if sentence_groups[-1].end_token_index != len(original_tokens) - 1:
            raise SentenceGroupCoverageMismatchError(
                "The final sentence group must terminate at the final original token."
            )
        if group_end_indexes != boundary_indexes:
            raise DecisionCoverageMismatchError(
                "Sentence groups must terminate on exactly the final boundary decisions."
            )


def postprocess_pa_probabilities(probability_result: PAProbabilityResult) -> PAPostProcessingResult:
    """Apply the exact recovered PA boundary post-processing and token grouping."""

    _validate_fixed_configuration()

    if not isinstance(probability_result, PAProbabilityResult):
        raise InvalidPAProbabilityResultError(
            "PA post-processing requires a PAProbabilityResult produced by Milestone 5A."
        )

    original_tokens, token_probabilities = _extract_probability_result_state(probability_result)
    if len(token_probabilities) != len(original_tokens):
        raise TokenCountMismatchError(
            "PA post-processing requires exactly one token-probability record per original token."
        )

    final_boundaries: list[bool] = []
    final_reasons: list[BoundaryDecisionReason] = []
    applied_thresholds: list[float] = []
    blended_probabilities: list[float] = []

    for expected_index, (token, token_probability) in enumerate(
        zip(original_tokens, token_probabilities, strict=True)
    ):
        if not isinstance(token_probability, TokenProbability):
            raise InvalidPAProbabilityResultError(
                "PA post-processing requires controlled TokenProbability records."
            )
        _validate_input_token_probability(token_probability)
        if token_probability.token_index != expected_index:
            raise TokenIndexMismatchError(
                "PA post-processing requires token indexes to remain sequential from 0."
            )
        if token_probability.token != token:
            raise TokenTextMismatchError(
                "PA post-processing requires token texts to match the original token sequence."
            )

        blended_probability = _validate_unit_interval(
            token_probability.blended_probability,
            exception_type=InvalidProbabilityValueError,
            message="PA post-processing requires finite blended probabilities within [0, 1].",
        )
        applied_threshold = (
            PUNCTUATION_THRESHOLD if token in PUNCTUATION_TOKENS else DEFAULT_THRESHOLD
        )
        decision_reason = (
            BoundaryDecisionReason.PUNCTUATION_THRESHOLD
            if token in PUNCTUATION_TOKENS
            else BoundaryDecisionReason.DEFAULT_THRESHOLD
        )

        final_boundaries.append(blended_probability >= applied_threshold)
        final_reasons.append(decision_reason)
        applied_thresholds.append(applied_threshold)
        blended_probabilities.append(blended_probability)

    for token_index, token in enumerate(original_tokens):
        if token in PARAGRAPH_MARKERS:
            final_boundaries[token_index] = False
            final_reasons[token_index] = BoundaryDecisionReason.PARAGRAPH_MARKER

    for token_index in range(len(original_tokens) - 1):
        if original_tokens[token_index + 1] in PARAGRAPH_MARKERS:
            final_boundaries[token_index] = True
            final_reasons[token_index] = BoundaryDecisionReason.BEFORE_PARAGRAPH

    final_index = len(original_tokens) - 1
    if not final_boundaries[final_index]:
        final_boundaries[final_index] = True
        final_reasons[final_index] = BoundaryDecisionReason.FORCE_LAST

    decisions = tuple(
        TokenBoundaryDecision(
            token_index=token_index,
            token=token,
            probability=blended_probabilities[token_index],
            applied_threshold=applied_thresholds[token_index],
            is_boundary=final_boundaries[token_index],
            decision_reason=final_reasons[token_index],
        )
        for token_index, token in enumerate(original_tokens)
    )
    sentence_groups = _build_sentence_groups(original_tokens, decisions)

    return PAPostProcessingResult(
        original_tokens=original_tokens,
        decisions=decisions,
        sentence_groups=sentence_groups,
        default_threshold=DEFAULT_THRESHOLD,
        punctuation_threshold=PUNCTUATION_THRESHOLD,
        punctuation_tokens=PUNCTUATION_TOKENS,
        paragraph_markers=PARAGRAPH_MARKERS,
        paragraph_rule_enabled=True,
        force_last_enabled=True,
    )


def _build_sentence_groups(
    original_tokens: tuple[str, ...],
    decisions: tuple[TokenBoundaryDecision, ...],
) -> tuple[SentenceTokenGroup, ...]:
    if not decisions or not decisions[-1].is_boundary:
        raise MissingFinalBoundaryError(
            "PA post-processing cannot build sentence groups without a final boundary."
        )

    sentence_groups: list[SentenceTokenGroup] = []
    start_index = 0
    for decision in decisions:
        if not decision.is_boundary:
            continue

        end_index = decision.token_index
        sentence_groups.append(
            SentenceTokenGroup(
                sentence_index=len(sentence_groups),
                start_token_index=start_index,
                end_token_index=end_index,
                tokens=original_tokens[start_index : end_index + 1],
                boundary_token_index=end_index,
                boundary_reason=decision.decision_reason,
            )
        )
        start_index = end_index + 1

    if start_index != len(original_tokens):
        raise SentenceGroupCoverageMismatchError(
            "Sentence grouping must cover every original token exactly once."
        )

    return tuple(sentence_groups)


def _extract_probability_result_state(
    probability_result: PAProbabilityResult,
) -> tuple[tuple[str, ...], tuple[TokenProbability, ...]]:
    original_sequence = getattr(probability_result, "original_tokens", None)
    if not isinstance(original_sequence, OriginalTokenSequence):
        raise InvalidPAProbabilityResultError(
            "PA post-processing requires a valid OriginalTokenSequence in the input result."
        )

    token_probabilities_raw = getattr(probability_result, "token_probabilities", None)
    try:
        token_probabilities = tuple(token_probabilities_raw)
    except TypeError as exc:
        raise InvalidPAProbabilityResultError(
            "PA post-processing requires an ordered token-probability collection."
        ) from exc

    return original_sequence.tokens, token_probabilities


def _validate_input_token_probability(token_probability: TokenProbability) -> None:
    if not isinstance(token_probability.token_index, int) or token_probability.token_index < 0:
        raise TokenIndexMismatchError(
            "PA post-processing requires non-negative token indexes."
        )
    if not isinstance(token_probability.token, str) or token_probability.token == "":
        raise TokenTextMismatchError(
            "PA post-processing requires non-empty token strings."
        )

    for field_name in ("base_probability", "micro_probability", "blended_probability"):
        _validate_unit_interval(
            getattr(token_probability, field_name),
            exception_type=InvalidProbabilityValueError,
            message="PA post-processing requires finite token probabilities within [0, 1].",
        )

    for field_name in ("base_observation_count", "micro_observation_count"):
        value = getattr(token_probability, field_name, None)
        if not isinstance(value, int) or value < 1:
            raise InvalidPAProbabilityResultError(
                "PA post-processing requires positive observation counts on token probabilities."
            )


def _validate_fixed_configuration() -> None:
    if not math.isclose(DEFAULT_THRESHOLD, 0.543, rel_tol=0.0, abs_tol=_FLOAT_TOLERANCE):
        raise InvalidThresholdConfigurationError(
            "Frozen PA default threshold must remain 0.543."
        )
    if not math.isclose(PUNCTUATION_THRESHOLD, 0.310, rel_tol=0.0, abs_tol=_FLOAT_TOLERANCE):
        raise InvalidThresholdConfigurationError(
            "Frozen PA punctuation threshold must remain 0.310."
        )
    if PUNCTUATION_TOKENS != (".", "؟", "?", "!", "…"):
        raise InvalidPunctuationConfigurationError(
            "Frozen PA punctuation tokens must remain the recovered exact tuple."
        )
    if PARAGRAPH_MARKERS != ("\\n", "\n", "[PAR]"):
        raise InvalidParagraphMarkerConfigurationError(
            "Frozen PA paragraph markers must remain the recovered exact tuple."
        )


def _validate_unit_interval(
    value: float,
    *,
    exception_type: type[Exception],
    message: str,
) -> float:
    if not isinstance(value, (int, float)):
        raise exception_type(message)

    numeric_value = float(value)
    if not math.isfinite(numeric_value) or not 0.0 <= numeric_value <= 1.0:
        raise exception_type(message)

    return numeric_value
