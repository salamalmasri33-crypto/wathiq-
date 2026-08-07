from __future__ import annotations

import inspect
from pathlib import Path
import sys
import unittest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.segmentation import (  # noqa: E402
    InvalidSegmentationInputError,
    LosslessUnicodeTokenSpanProvider,
    RawTextTokenSpanProvider,
    SegmentationToken,
)
from wathiq_araseg.segmentation import token_provider as token_provider_module  # noqa: E402


class LosslessUnicodeTokenSpanProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = LosslessUnicodeTokenSpanProvider()

    def test_provider_implements_the_minimal_raw_text_abstraction(self) -> None:
        self.assertIsInstance(self.provider, RawTextTokenSpanProvider)

    def test_empty_text_returns_an_empty_immutable_token_collection(self) -> None:
        tokens = self.provider.provide("")

        self.assertEqual(tokens, ())
        self.assertIsInstance(tokens, tuple)

    def test_whitespace_only_text_preserves_gaps_without_emitting_tokens(self) -> None:
        tokens = self.provider.provide(" \t\u00a0 ")

        self.assertEqual(tokens, ())

    def test_required_example_one_splits_attached_period_from_arabic_and_digits(self) -> None:
        source = "صدر القرار رقم 25."

        tokens = self.provider.provide(source)

        self.assertEqual(_token_texts(tokens), ("صدر", "القرار", "رقم", "25", "."))
        _assert_exact_source_slices(self, source, tokens)

    def test_required_example_two_splits_repeated_punctuation_and_arabic_question_mark(self) -> None:
        source = "مرحباً... كيف حالك؟"

        tokens = self.provider.provide(source)

        self.assertEqual(_token_texts(tokens), ("مرحباً", ".", ".", ".", "كيف", "حالك", "؟"))
        _assert_exact_source_slices(self, source, tokens)

    def test_required_example_three_emits_actual_lf_as_one_atomic_token(self) -> None:
        source = "السطر الأول\nالسطر الثاني"

        tokens = self.provider.provide(source)
        lf_index = source.index("\n")

        self.assertEqual(_token_texts(tokens), ("السطر", "الأول", "\n", "السطر", "الثاني"))
        self.assertEqual(
            tokens[2],
            SegmentationToken(index=2, text="\n", start_offset=lf_index, end_offset=lf_index + 1),
        )
        _assert_exact_source_slices(self, source, tokens)

    def test_literal_backslash_n_and_literal_paragraph_marker_remain_atomic_tokens(self) -> None:
        source = "أ \\n [PAR] ب"

        tokens = self.provider.provide(source)

        self.assertEqual(_token_texts(tokens), ("أ", "\\n", "[PAR]", "ب"))
        _assert_exact_source_slices(self, source, tokens)

    def test_boundary_markers_at_source_edges_and_bare_backslash_follow_exact_matching_rules(self) -> None:
        cases = (
            ("[PAR]نهاية", ("[PAR]", "نهاية")),
            ("بداية\\n", ("بداية", "\\n")),
            ("\\x", ("\\", "x")),
        )

        for source, expected_tokens in cases:
            with self.subTest(source=source):
                tokens = self.provider.provide(source)
                self.assertEqual(_token_texts(tokens), expected_tokens)
                _assert_exact_source_slices(self, source, tokens)

    def test_leading_trailing_repeated_spaces_and_tabs_remain_recoverable_as_gaps(self) -> None:
        source = "  هذا   \tنص  "

        tokens = self.provider.provide(source)

        self.assertEqual(_token_texts(tokens), ("هذا", "نص"))
        self.assertEqual(tokens[0].start_offset, 2)
        self.assertEqual(tokens[0].end_offset, 5)
        self.assertEqual(tokens[1].start_offset, 9)
        self.assertEqual(tokens[1].end_offset, 11)
        _assert_exact_source_slices(self, source, tokens)

    def test_repeated_actual_lf_tokens_are_preserved_exactly(self) -> None:
        source = "أ\n\nب"

        tokens = self.provider.provide(source)

        self.assertEqual(_token_texts(tokens), ("أ", "\n", "\n", "ب"))
        _assert_exact_source_slices(self, source, tokens)

    def test_arabic_diacritics_digits_and_punctuation_are_preserved_without_normalization(self) -> None:
        source = "مُحَمَّد ١٢٣, 456،"

        tokens = self.provider.provide(source)

        self.assertEqual(_token_texts(tokens), ("مُحَمَّد", "١٢٣", ",", "456", "،"))
        _assert_exact_source_slices(self, source, tokens)

    def test_opening_and_closing_punctuation_are_separate_tokens(self) -> None:
        source = "«نص» (اختبار)"

        tokens = self.provider.provide(source)

        self.assertEqual(_token_texts(tokens), ("«", "نص", "»", "(", "اختبار", ")"))
        _assert_exact_source_slices(self, source, tokens)

    def test_symbols_and_emoji_are_preserved_inside_normal_tokens(self) -> None:
        source = "رمز🙂✓ +42"

        tokens = self.provider.provide(source)

        self.assertEqual(_token_texts(tokens), ("رمز🙂✓", "+42"))
        _assert_exact_source_slices(self, source, tokens)

    def test_repeated_identical_words_remain_distinct_by_exact_offsets(self) -> None:
        source = "كلمة كلمة كلمة"

        tokens = self.provider.provide(source)

        self.assertEqual(_token_texts(tokens), ("كلمة", "كلمة", "كلمة"))
        self.assertEqual(
            tuple((token.start_offset, token.end_offset) for token in tokens),
            ((0, 4), (5, 9), (10, 14)),
        )
        _assert_exact_source_slices(self, source, tokens)

    def test_non_whitespace_source_characters_are_not_silently_dropped(self) -> None:
        source = "A[PAR]B\\nC...D🙂"

        tokens = self.provider.provide(source)

        self.assertEqual(_token_texts(tokens), ("A", "[PAR]", "B", "\\n", "C", ".", ".", ".", "D🙂"))
        reconstructed_non_gap_text = "".join(token.text for token in tokens if token.text != "\n")
        self.assertEqual(reconstructed_non_gap_text, "A[PAR]B\\nC...D🙂")
        _assert_exact_source_slices(self, source, tokens)

    def test_cr_is_rejected_without_normalizing_the_source(self) -> None:
        with self.assertRaises(InvalidSegmentationInputError):
            self.provider.provide("أ\rب")

    def test_crlf_is_rejected_without_normalizing_the_source(self) -> None:
        with self.assertRaises(InvalidSegmentationInputError):
            self.provider.provide("أ\r\nب")

    def test_provider_is_deterministic_across_repeated_execution(self) -> None:
        source = "  مرحباً... كيف حالك؟\n\\n[PAR]  "

        first = self.provider.provide(source)
        second = self.provider.provide(source)

        self.assertEqual(first, second)

    def test_source_contains_no_forbidden_shortcuts_or_model_specific_tokenizers(self) -> None:
        source = inspect.getsource(token_provider_module)

        for forbidden_snippet in (
            ".split(",
            "splitlines(",
            "re.",
            "camel",
            "from_pretrained",
            "AutoTokenizer",
        ):
            with self.subTest(forbidden_snippet=forbidden_snippet):
                self.assertNotIn(forbidden_snippet, source)


def _token_texts(tokens: tuple[SegmentationToken, ...]) -> tuple[str, ...]:
    return tuple(token.text for token in tokens)


def _assert_exact_source_slices(
    test_case: unittest.TestCase,
    source: str,
    tokens: tuple[SegmentationToken, ...],
) -> None:
    previous_end_offset = -1
    for expected_index, token in enumerate(tokens):
        test_case.assertEqual(token.index, expected_index)
        test_case.assertEqual(source[token.start_offset : token.end_offset], token.text)
        test_case.assertGreaterEqual(token.start_offset, 0)
        test_case.assertGreater(token.end_offset, token.start_offset)
        test_case.assertGreaterEqual(token.start_offset, previous_end_offset)
        previous_end_offset = token.end_offset


if __name__ == "__main__":
    unittest.main()
