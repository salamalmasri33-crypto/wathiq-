from __future__ import annotations

import inspect
import math
from pathlib import Path
import sys
import unittest
from unittest import mock

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.pa.exceptions import (  # noqa: E402
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
from wathiq_araseg.pa.models import (  # noqa: E402
    OriginalTokenSequence,
    PAProbabilityResult,
    TokenProbability,
)
from wathiq_araseg.pa.postprocessing import (  # noqa: E402
    DEFAULT_THRESHOLD,
    PARAGRAPH_MARKERS,
    PUNCTUATION_THRESHOLD,
    PUNCTUATION_TOKENS,
    BoundaryDecisionReason,
    PAPostProcessingResult,
    SentenceTokenGroup,
    TokenBoundaryDecision,
    postprocess_pa_probabilities,
)
from wathiq_araseg.pa import postprocessing as postprocessing_module  # noqa: E402


class PAPostProcessingThresholdTests(unittest.TestCase):
    def test_normal_tokens_use_default_threshold_without_rounding(self) -> None:
        cases = (
            (DEFAULT_THRESHOLD - 0.001, False),
            (DEFAULT_THRESHOLD, True),
            (DEFAULT_THRESHOLD + 0.001, True),
            (0.542999999999, False),
        )

        for probability, expected_boundary in cases:
            with self.subTest(probability=probability):
                result = _run_postprocessing(("عادي", "ختام"), (probability, 0.9))
                decision = result.decisions[0]

                self.assertEqual(decision.applied_threshold, DEFAULT_THRESHOLD)
                self.assertEqual(decision.is_boundary, expected_boundary)
                self.assertIs(
                    decision.decision_reason,
                    BoundaryDecisionReason.DEFAULT_THRESHOLD,
                )

    def test_exact_punctuation_tokens_use_punctuation_threshold(self) -> None:
        probabilities = (
            (PUNCTUATION_THRESHOLD - 0.001, False),
            (PUNCTUATION_THRESHOLD, True),
            (PUNCTUATION_THRESHOLD + 0.001, True),
            (0.4, True),
        )

        for token in PUNCTUATION_TOKENS:
            for probability, expected_boundary in probabilities:
                with self.subTest(token=token, probability=probability):
                    result = _run_postprocessing((token, "ختام"), (probability, 0.9))
                    decision = result.decisions[0]

                    self.assertEqual(decision.applied_threshold, PUNCTUATION_THRESHOLD)
                    self.assertEqual(decision.is_boundary, expected_boundary)
                    self.assertIs(
                        decision.decision_reason,
                        BoundaryDecisionReason.PUNCTUATION_THRESHOLD,
                    )

    def test_same_probability_differs_between_punctuation_and_normal_tokens(self) -> None:
        punctuation_result = _run_postprocessing((".", "ختام"), (0.4, 0.9))
        normal_result = _run_postprocessing(("كلمة", "ختام"), (0.4, 0.9))

        self.assertTrue(punctuation_result.decisions[0].is_boundary)
        self.assertFalse(normal_result.decisions[0].is_boundary)

    def test_non_punctuation_tokens_do_not_use_punctuation_threshold(self) -> None:
        non_punctuation_tokens = (
            "،",
            ",",
            ":",
            ";",
            "؛",
            "..",
            "...",
            "؟ ",
            " !",
            "سؤال؟",
            "!"
            "لاحق",
        )

        for token in non_punctuation_tokens:
            with self.subTest(token=token):
                result = _run_postprocessing((token, "ختام"), (0.4, 0.9))
                decision = result.decisions[0]

                self.assertEqual(decision.applied_threshold, DEFAULT_THRESHOLD)
                self.assertFalse(decision.is_boundary)
                self.assertIs(
                    decision.decision_reason,
                    BoundaryDecisionReason.DEFAULT_THRESHOLD,
                )


class PAPostProcessingParagraphRuleTests(unittest.TestCase):
    def test_middle_paragraph_markers_are_forced_false_and_preceded_by_boundary(self) -> None:
        for marker in PARAGRAPH_MARKERS:
            for probability in (0.1, 0.9):
                with self.subTest(marker=marker, probability=probability):
                    result = _run_postprocessing(("قبل", marker, "بعد"), (0.2, probability, 0.2))

                    self.assertTrue(result.decisions[0].is_boundary)
                    self.assertIs(
                        result.decisions[0].decision_reason,
                        BoundaryDecisionReason.BEFORE_PARAGRAPH,
                    )
                    self.assertFalse(result.decisions[1].is_boundary)
                    self.assertIs(
                        result.decisions[1].decision_reason,
                        BoundaryDecisionReason.PARAGRAPH_MARKER,
                    )
                    self.assertEqual(result.decisions[1].token, marker)
                    self.assertEqual(result.sentence_groups[1].tokens[0], marker)

    def test_paragraph_marker_at_beginning_is_forced_false_when_not_final(self) -> None:
        result = _run_postprocessing(("\n", "بعد"), (0.95, 0.2))

        self.assertFalse(result.decisions[0].is_boundary)
        self.assertIs(
            result.decisions[0].decision_reason,
            BoundaryDecisionReason.PARAGRAPH_MARKER,
        )
        self.assertTrue(result.decisions[1].is_boundary)

    def test_paragraph_marker_at_end_is_forced_true_by_force_last(self) -> None:
        for marker in PARAGRAPH_MARKERS:
            with self.subTest(marker=marker):
                result = _run_postprocessing(("قبل", marker), (0.2, 0.95))

                self.assertTrue(result.decisions[0].is_boundary)
                self.assertIs(
                    result.decisions[0].decision_reason,
                    BoundaryDecisionReason.BEFORE_PARAGRAPH,
                )
                self.assertTrue(result.decisions[1].is_boundary)
                self.assertIs(
                    result.decisions[1].decision_reason,
                    BoundaryDecisionReason.FORCE_LAST,
                )

    def test_single_token_paragraph_markers_end_with_force_last(self) -> None:
        for marker in PARAGRAPH_MARKERS:
            with self.subTest(marker=marker):
                result = _run_postprocessing((marker,), (0.0,))
                decision = result.decisions[0]

                self.assertTrue(decision.is_boundary)
                self.assertIs(decision.decision_reason, BoundaryDecisionReason.FORCE_LAST)
                self.assertEqual(result.sentence_groups[0].tokens, (marker,))

    def test_consecutive_paragraph_markers_follow_historical_precedence(self) -> None:
        result = _run_postprocessing(("أ", "\n", "[PAR]", "ب"), (0.1, 0.9, 0.9, 0.1))

        self.assertEqual(
            tuple(decision.is_boundary for decision in result.decisions),
            (True, True, False, True),
        )
        self.assertEqual(
            tuple(decision.decision_reason for decision in result.decisions),
            (
                BoundaryDecisionReason.BEFORE_PARAGRAPH,
                BoundaryDecisionReason.BEFORE_PARAGRAPH,
                BoundaryDecisionReason.PARAGRAPH_MARKER,
                BoundaryDecisionReason.FORCE_LAST,
            ),
        )
        self.assertEqual(
            tuple(group.tokens for group in result.sentence_groups),
            (("أ",), ("\n",), ("[PAR]", "ب")),
        )

    def test_three_consecutive_paragraph_markers_follow_exact_assignment_order(self) -> None:
        tokens = ("أ", "\n", "\\n", "[PAR]", "ب")
        result = _run_postprocessing(tokens, (0.1, 0.95, 0.95, 0.95, 0.2))

        self.assertEqual(
            tuple(decision.is_boundary for decision in result.decisions),
            (True, True, True, False, True),
        )
        self.assertEqual(
            tuple(decision.decision_reason for decision in result.decisions),
            (
                BoundaryDecisionReason.BEFORE_PARAGRAPH,
                BoundaryDecisionReason.BEFORE_PARAGRAPH,
                BoundaryDecisionReason.BEFORE_PARAGRAPH,
                BoundaryDecisionReason.PARAGRAPH_MARKER,
                BoundaryDecisionReason.FORCE_LAST,
            ),
        )


class PAPostProcessingForceLastTests(unittest.TestCase):
    def test_final_low_probability_normal_token_is_forced_last(self) -> None:
        result = _run_postprocessing(("أول", "آخر"), (0.1, 0.2))

        self.assertTrue(result.decisions[-1].is_boundary)
        self.assertIs(result.decisions[-1].decision_reason, BoundaryDecisionReason.FORCE_LAST)

    def test_final_normal_token_already_true_preserves_default_reason(self) -> None:
        result = _run_postprocessing(("أول", "آخر"), (0.1, DEFAULT_THRESHOLD))

        self.assertTrue(result.decisions[-1].is_boundary)
        self.assertIs(
            result.decisions[-1].decision_reason,
            BoundaryDecisionReason.DEFAULT_THRESHOLD,
        )

    def test_final_punctuation_already_true_preserves_punctuation_reason(self) -> None:
        result = _run_postprocessing(("أول", "!"), (0.1, PUNCTUATION_THRESHOLD))

        self.assertTrue(result.decisions[-1].is_boundary)
        self.assertIs(
            result.decisions[-1].decision_reason,
            BoundaryDecisionReason.PUNCTUATION_THRESHOLD,
        )

    def test_exactly_one_final_decision_record_exists(self) -> None:
        result = _run_postprocessing(("أ", "ب", "ج"), (0.1, 0.1, 0.1))

        self.assertEqual(len(result.decisions), 3)
        self.assertEqual(result.decisions[-1].token_index, 2)
        self.assertTrue(result.decisions[-1].is_boundary)


class PAPostProcessingGroupingTests(unittest.TestCase):
    def test_one_sentence_group_covers_all_tokens(self) -> None:
        result = _run_postprocessing(("أ", "ب", "ج"), (0.1, 0.1, 0.1))

        self.assertEqual(len(result.sentence_groups), 1)
        self.assertEqual(result.sentence_groups[0].tokens, ("أ", "ب", "ج"))
        self.assertEqual(result.sentence_groups[0].start_token_index, 0)
        self.assertEqual(result.sentence_groups[0].end_token_index, 2)

    def test_multiple_sentence_groups_preserve_terminating_boundaries(self) -> None:
        result = _run_postprocessing(("أ", ".", "ب", "ج"), (0.1, 0.4, 0.2, 0.1))

        self.assertEqual(
            tuple(group.tokens for group in result.sentence_groups),
            (("أ", "."), ("ب", "ج")),
        )
        self.assertEqual(
            tuple(group.boundary_reason for group in result.sentence_groups),
            (
                BoundaryDecisionReason.PUNCTUATION_THRESHOLD,
                BoundaryDecisionReason.FORCE_LAST,
            ),
        )

    def test_paragraph_marker_begins_following_group_when_not_a_boundary(self) -> None:
        result = _run_postprocessing(("قبل", "\n", "بعد"), (0.1, 0.2, 0.1))

        self.assertEqual(
            tuple(group.tokens for group in result.sentence_groups),
            (("قبل",), ("\n", "بعد")),
        )

    def test_consecutive_paragraph_markers_do_not_create_empty_groups(self) -> None:
        result = _run_postprocessing(("أ", "\n", "[PAR]", "ب"), (0.1, 0.2, 0.2, 0.1))

        self.assertEqual(
            tuple(group.tokens for group in result.sentence_groups),
            (("أ",), ("\n",), ("[PAR]", "ب")),
        )
        self.assertTrue(all(group.tokens for group in result.sentence_groups))

    def test_sentence_group_metadata_is_exact(self) -> None:
        result = _run_postprocessing(("أ", ".", "\n", "ب", "؟"), (0.1, 0.4, 0.2, 0.2, 0.31))

        self.assertEqual(
            [
                (
                    group.sentence_index,
                    group.start_token_index,
                    group.end_token_index,
                    group.boundary_token_index,
                    group.boundary_reason,
                )
                for group in result.sentence_groups
            ],
            [
                (0, 0, 1, 1, BoundaryDecisionReason.BEFORE_PARAGRAPH),
                (1, 2, 4, 4, BoundaryDecisionReason.PUNCTUATION_THRESHOLD),
            ],
        )

    def test_postprocessing_is_deterministic(self) -> None:
        tokens = ("كلمة", ".", "\n", "\\n", "[PAR]", "خاتمة")
        probabilities = (0.2, 0.4, 0.9, 0.8, 0.7, 0.1)

        first = _run_postprocessing(tokens, probabilities)
        second = _run_postprocessing(tokens, probabilities)

        self.assertEqual(first, second)


class PAPostProcessingValidationTests(unittest.TestCase):
    def test_blended_probability_only_drives_decisioning(self) -> None:
        result = _run_postprocessing(
            ("أ", "خاتمة"),
            (0.2, 0.1),
            base_probabilities=(0.95, 0.1),
            micro_probabilities=(0.95, 0.1),
        )

        self.assertFalse(result.decisions[0].is_boundary)
        self.assertIs(
            result.decisions[0].decision_reason,
            BoundaryDecisionReason.DEFAULT_THRESHOLD,
        )

    def test_invalid_blended_probabilities_are_rejected(self) -> None:
        for invalid_probability in (float("nan"), -0.1, 1.1):
            with self.subTest(probability=invalid_probability):
                broken_result = _make_invalid_probability_result(
                    original_tokens=OriginalTokenSequence(("أ",)),
                    token_probabilities=(
                        _make_invalid_token_probability(
                            token_index=0,
                            token="أ",
                            blended_probability=invalid_probability,
                        ),
                    ),
                )

                with self.assertRaises(InvalidProbabilityValueError):
                    postprocess_pa_probabilities(broken_result)

    def test_invalid_observation_counts_are_rejected(self) -> None:
        broken_result = _make_invalid_probability_result(
            original_tokens=OriginalTokenSequence(("أ",)),
            token_probabilities=(
                _make_invalid_token_probability(
                    token_index=0,
                    token="أ",
                    base_observation_count=0,
                ),
            ),
        )

        with self.assertRaises(InvalidPAProbabilityResultError):
            postprocess_pa_probabilities(broken_result)

    def test_missing_and_extra_probability_records_are_rejected(self) -> None:
        missing_result = _make_invalid_probability_result(
            original_tokens=OriginalTokenSequence(("أ", "ب")),
            token_probabilities=(
                _make_valid_token_probability(0, "أ", 0.2),
            ),
        )
        extra_result = _make_invalid_probability_result(
            original_tokens=OriginalTokenSequence(("أ",)),
            token_probabilities=(
                _make_valid_token_probability(0, "أ", 0.2),
                _make_valid_token_probability(1, "ب", 0.2),
            ),
        )

        with self.assertRaises(TokenCountMismatchError):
            postprocess_pa_probabilities(missing_result)
        with self.assertRaises(TokenCountMismatchError):
            postprocess_pa_probabilities(extra_result)

    def test_duplicate_and_non_sequential_token_indexes_are_rejected(self) -> None:
        duplicate_index_result = _make_invalid_probability_result(
            original_tokens=OriginalTokenSequence(("أ", "ب")),
            token_probabilities=(
                _make_valid_token_probability(0, "أ", 0.2),
                _make_valid_token_probability(0, "ب", 0.2),
            ),
        )
        skipped_index_result = _make_invalid_probability_result(
            original_tokens=OriginalTokenSequence(("أ", "ب")),
            token_probabilities=(
                _make_valid_token_probability(0, "أ", 0.2),
                _make_valid_token_probability(2, "ب", 0.2),
            ),
        )

        with self.assertRaises(TokenIndexMismatchError):
            postprocess_pa_probabilities(duplicate_index_result)
        with self.assertRaises(TokenIndexMismatchError):
            postprocess_pa_probabilities(skipped_index_result)

    def test_token_text_and_original_token_shape_mismatches_are_rejected(self) -> None:
        mismatched_text_result = _make_invalid_probability_result(
            original_tokens=OriginalTokenSequence(("أ",)),
            token_probabilities=(
                _make_valid_token_probability(0, "ب", 0.2),
            ),
        )
        bad_original_tokens_result = _make_invalid_probability_result(
            original_tokens=("أ",),
            token_probabilities=(
                _make_valid_token_probability(0, "أ", 0.2),
            ),
        )

        with self.assertRaises(TokenTextMismatchError):
            postprocess_pa_probabilities(mismatched_text_result)
        with self.assertRaises(InvalidPAProbabilityResultError):
            postprocess_pa_probabilities(bad_original_tokens_result)

    def test_invalid_fixed_configuration_is_rejected(self) -> None:
        valid_result = _build_probability_result(("أ",), (0.1,))

        with mock.patch.object(postprocessing_module, "DEFAULT_THRESHOLD", 1.1):
            with self.assertRaises(InvalidThresholdConfigurationError):
                postprocess_pa_probabilities(valid_result)

        with mock.patch.object(postprocessing_module, "PUNCTUATION_TOKENS", (".", "؟")):
            with self.assertRaises(InvalidPunctuationConfigurationError):
                postprocess_pa_probabilities(valid_result)

        with mock.patch.object(postprocessing_module, "PARAGRAPH_MARKERS", ("\n",)):
            with self.assertRaises(InvalidParagraphMarkerConfigurationError):
                postprocess_pa_probabilities(valid_result)

    def test_postprocessing_result_validation_rejects_missing_final_boundary(self) -> None:
        decisions = (
            TokenBoundaryDecision(
                token_index=0,
                token="أ",
                probability=0.1,
                applied_threshold=DEFAULT_THRESHOLD,
                is_boundary=False,
                decision_reason=BoundaryDecisionReason.DEFAULT_THRESHOLD,
            ),
        )
        groups = (
            SentenceTokenGroup(
                sentence_index=0,
                start_token_index=0,
                end_token_index=0,
                tokens=("أ",),
                boundary_token_index=0,
                boundary_reason=BoundaryDecisionReason.DEFAULT_THRESHOLD,
            ),
        )

        with self.assertRaises(MissingFinalBoundaryError):
            PAPostProcessingResult(
                original_tokens=("أ",),
                decisions=decisions,
                sentence_groups=groups,
                default_threshold=DEFAULT_THRESHOLD,
                punctuation_threshold=PUNCTUATION_THRESHOLD,
                punctuation_tokens=PUNCTUATION_TOKENS,
                paragraph_markers=PARAGRAPH_MARKERS,
                paragraph_rule_enabled=True,
                force_last_enabled=True,
            )

    def test_postprocessing_result_validation_rejects_bad_sentence_coverage(self) -> None:
        decisions = (
            TokenBoundaryDecision(
                token_index=0,
                token="أ",
                probability=0.8,
                applied_threshold=DEFAULT_THRESHOLD,
                is_boundary=True,
                decision_reason=BoundaryDecisionReason.DEFAULT_THRESHOLD,
            ),
            TokenBoundaryDecision(
                token_index=1,
                token="ب",
                probability=0.8,
                applied_threshold=DEFAULT_THRESHOLD,
                is_boundary=True,
                decision_reason=BoundaryDecisionReason.DEFAULT_THRESHOLD,
            ),
        )
        bad_groups = (
            SentenceTokenGroup(
                sentence_index=0,
                start_token_index=0,
                end_token_index=0,
                tokens=("أ",),
                boundary_token_index=0,
                boundary_reason=BoundaryDecisionReason.DEFAULT_THRESHOLD,
            ),
        )

        with self.assertRaises(SentenceGroupCoverageMismatchError):
            PAPostProcessingResult(
                original_tokens=("أ", "ب"),
                decisions=decisions,
                sentence_groups=bad_groups,
                default_threshold=DEFAULT_THRESHOLD,
                punctuation_threshold=PUNCTUATION_THRESHOLD,
                punctuation_tokens=PUNCTUATION_TOKENS,
                paragraph_markers=PARAGRAPH_MARKERS,
                paragraph_rule_enabled=True,
                force_last_enabled=True,
            )

    def test_postprocessing_result_validation_rejects_decision_group_mismatch(self) -> None:
        decisions = (
            TokenBoundaryDecision(
                token_index=0,
                token="أ",
                probability=0.8,
                applied_threshold=DEFAULT_THRESHOLD,
                is_boundary=True,
                decision_reason=BoundaryDecisionReason.DEFAULT_THRESHOLD,
            ),
            TokenBoundaryDecision(
                token_index=1,
                token="ب",
                probability=0.8,
                applied_threshold=DEFAULT_THRESHOLD,
                is_boundary=True,
                decision_reason=BoundaryDecisionReason.DEFAULT_THRESHOLD,
            ),
        )
        bad_groups = (
            SentenceTokenGroup(
                sentence_index=0,
                start_token_index=0,
                end_token_index=1,
                tokens=("أ", "ب"),
                boundary_token_index=1,
                boundary_reason=BoundaryDecisionReason.DEFAULT_THRESHOLD,
            ),
        )

        with self.assertRaises(DecisionCoverageMismatchError):
            PAPostProcessingResult(
                original_tokens=("أ", "ب"),
                decisions=decisions,
                sentence_groups=bad_groups,
                default_threshold=DEFAULT_THRESHOLD,
                punctuation_threshold=PUNCTUATION_THRESHOLD,
                punctuation_tokens=PUNCTUATION_TOKENS,
                paragraph_markers=PARAGRAPH_MARKERS,
                paragraph_rule_enabled=True,
                force_last_enabled=True,
            )

    def test_postprocessing_is_separate_from_inference_stack(self) -> None:
        signature = inspect.signature(postprocess_pa_probabilities)
        source = inspect.getsource(postprocessing_module)
        result = _run_postprocessing(("أ", "ب"), (0.1, 0.1))

        self.assertEqual(tuple(signature.parameters.keys()), ("probability_result",))
        self.assertEqual(len(result.decisions), 2)
        self.assertNotIn("transformers", source)
        self.assertNotIn("torch.inference_mode", source)
        self.assertNotIn("PAEnsembleWindowInferenceEngine", source)
        self.assertNotIn("build_first_subtoken_alignment", source)


def _run_postprocessing(
    tokens: tuple[str, ...],
    blended_probabilities: tuple[float, ...],
    *,
    base_probabilities: tuple[float, ...] | None = None,
    micro_probabilities: tuple[float, ...] | None = None,
) -> PAPostProcessingResult:
    return postprocess_pa_probabilities(
        _build_probability_result(
            tokens,
            blended_probabilities,
            base_probabilities=base_probabilities,
            micro_probabilities=micro_probabilities,
        )
    )


def _build_probability_result(
    tokens: tuple[str, ...],
    blended_probabilities: tuple[float, ...],
    *,
    base_probabilities: tuple[float, ...] | None = None,
    micro_probabilities: tuple[float, ...] | None = None,
) -> PAProbabilityResult:
    original_tokens = OriginalTokenSequence(tokens)
    base_probabilities = base_probabilities or blended_probabilities
    micro_probabilities = micro_probabilities or blended_probabilities

    token_probabilities = tuple(
        TokenProbability(
            token_index=index,
            token=token,
            base_probability=base_probabilities[index],
            micro_probability=micro_probabilities[index],
            blended_probability=blended_probabilities[index],
            base_observation_count=1,
            micro_observation_count=1,
        )
        for index, token in enumerate(tokens)
    )

    return PAProbabilityResult(
        original_tokens=original_tokens,
        token_probabilities=token_probabilities,
        window_count=1,
        max_length=512,
        stride=64,
        base_weight=0.95,
        micro_weight=0.05,
    )


def _make_valid_token_probability(
    token_index: int,
    token: str,
    blended_probability: float,
) -> TokenProbability:
    return TokenProbability(
        token_index=token_index,
        token=token,
        base_probability=0.1,
        micro_probability=0.1,
        blended_probability=blended_probability,
        base_observation_count=1,
        micro_observation_count=1,
    )


def _make_invalid_token_probability(
    *,
    token_index: int,
    token: str,
    base_probability: float = 0.1,
    micro_probability: float = 0.1,
    blended_probability: float = 0.1,
    base_observation_count: int = 1,
    micro_observation_count: int = 1,
) -> TokenProbability:
    token_probability = object.__new__(TokenProbability)
    object.__setattr__(token_probability, "token_index", token_index)
    object.__setattr__(token_probability, "token", token)
    object.__setattr__(token_probability, "base_probability", base_probability)
    object.__setattr__(token_probability, "micro_probability", micro_probability)
    object.__setattr__(token_probability, "blended_probability", blended_probability)
    object.__setattr__(token_probability, "base_observation_count", base_observation_count)
    object.__setattr__(token_probability, "micro_observation_count", micro_observation_count)
    return token_probability


def _make_invalid_probability_result(
    *,
    original_tokens,
    token_probabilities,
) -> PAProbabilityResult:
    probability_result = object.__new__(PAProbabilityResult)
    object.__setattr__(probability_result, "original_tokens", original_tokens)
    object.__setattr__(probability_result, "token_probabilities", token_probabilities)
    object.__setattr__(probability_result, "window_count", 1)
    object.__setattr__(probability_result, "max_length", 512)
    object.__setattr__(probability_result, "stride", 64)
    object.__setattr__(probability_result, "base_weight", 0.95)
    object.__setattr__(probability_result, "micro_weight", 0.05)
    return probability_result


if __name__ == "__main__":
    unittest.main()
