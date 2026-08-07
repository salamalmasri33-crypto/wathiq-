from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
import unittest

import torch

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.pa import (  # noqa: E402
    InvalidOriginalTokenSequenceError,
    InvalidWordIdError,
    MissingTokenObservationError,
    OriginalTokenSequence,
    UnsupportedTokenizerBehaviorError,
    build_first_subtoken_alignment,
)


class OriginalTokenSequenceTests(unittest.TestCase):
    def test_empty_token_sequence_is_rejected(self) -> None:
        with self.assertRaises(InvalidOriginalTokenSequenceError):
            OriginalTokenSequence(())

    def test_empty_string_token_is_rejected(self) -> None:
        with self.assertRaises(InvalidOriginalTokenSequenceError):
            OriginalTokenSequence(("هذا", "", "نص"))

    def test_whitespace_containing_tokens_are_preserved_without_stripping(self) -> None:
        sequence = OriginalTokenSequence(("  كلمة  ", "\n", "[PAR]"))

        self.assertEqual(sequence.tokens, ("  كلمة  ", "\n", "[PAR]"))

    def test_punctuation_newline_and_par_tokens_are_preserved(self) -> None:
        sequence = OriginalTokenSequence(("؟", "\n", "[PAR]", "."))

        self.assertEqual(sequence.tokens, ("؟", "\n", "[PAR]", "."))

    def test_input_tokens_are_stored_as_an_immutable_tuple_in_original_order(self) -> None:
        raw_tokens = ["هذا", "نص", "مرتب"]
        sequence = OriginalTokenSequence(raw_tokens)
        raw_tokens[0] = "مختلف"

        self.assertIsInstance(sequence.tokens, tuple)
        self.assertEqual(sequence.tokens, ("هذا", "نص", "مرتب"))
        with self.assertRaises(FrozenInstanceError):
            sequence.tokens = ("بديل",)


class AlignmentTests(unittest.TestCase):
    def test_alignment_calls_tokenizer_with_required_overflow_options(self) -> None:
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[[101, 11, 12, 102]],
                word_ids_by_window=[[None, 0, 1, None]],
            )
        )
        original_tokens = OriginalTokenSequence(("هذا", "نص"))

        build_first_subtoken_alignment(
            tokenizer,
            original_tokens,
            max_length=512,
            stride=64,
        )

        self.assertEqual(tokenizer.calls[0]["tokens"], ("هذا", "نص"))
        self.assertTrue(tokenizer.calls[0]["kwargs"]["is_split_into_words"])
        self.assertTrue(tokenizer.calls[0]["kwargs"]["truncation"])
        self.assertEqual(tokenizer.calls[0]["kwargs"]["max_length"], 512)
        self.assertEqual(tokenizer.calls[0]["kwargs"]["stride"], 64)
        self.assertTrue(tokenizer.calls[0]["kwargs"]["return_overflowing_tokens"])
        self.assertEqual(tokenizer.calls[0]["kwargs"]["return_tensors"], "pt")
        self.assertTrue(tokenizer.calls[0]["kwargs"]["padding"])

    def test_actual_newline_token_is_mapped_to_par_for_model_input(self) -> None:
        tokenizer = _FakeTokenizer(_build_identity_encoding(3))
        original_tokens = OriginalTokenSequence(("قبل", "\n", "بعد"))

        alignment = build_first_subtoken_alignment(
            tokenizer,
            original_tokens,
            max_length=512,
            stride=64,
        )

        self.assertEqual(tokenizer.calls[0]["tokens"], ("قبل", "[PAR]", "بعد"))
        self.assertEqual(alignment.original_tokens.tokens, ("قبل", "\n", "بعد"))
        self.assertEqual(alignment.windows[0].original_token_indexes, (0, 1, 2))

    def test_literal_backslash_n_token_is_mapped_to_par_for_model_input(self) -> None:
        tokenizer = _FakeTokenizer(_build_identity_encoding(3))
        original_tokens = OriginalTokenSequence(("قبل", "\\n", "بعد"))

        alignment = build_first_subtoken_alignment(
            tokenizer,
            original_tokens,
            max_length=512,
            stride=64,
        )

        self.assertEqual(tokenizer.calls[0]["tokens"], ("قبل", "[PAR]", "بعد"))
        self.assertEqual(alignment.original_tokens.tokens, ("قبل", "\\n", "بعد"))
        self.assertEqual(alignment.windows[0].original_token_indexes, (0, 1, 2))

    def test_existing_par_token_remains_par_for_model_input(self) -> None:
        tokenizer = _FakeTokenizer(_build_identity_encoding(3))
        original_tokens = OriginalTokenSequence(("قبل", "[PAR]", "بعد"))

        alignment = build_first_subtoken_alignment(
            tokenizer,
            original_tokens,
            max_length=512,
            stride=64,
        )

        self.assertEqual(tokenizer.calls[0]["tokens"], ("قبل", "[PAR]", "بعد"))
        self.assertEqual(alignment.original_tokens.tokens, ("قبل", "[PAR]", "بعد"))
        self.assertEqual(alignment.windows[0].original_token_indexes, (0, 1, 2))

    def test_mixed_paragraph_representations_are_mapped_one_to_one(self) -> None:
        tokenizer = _FakeTokenizer(_build_identity_encoding(7))
        original_tokens = OriginalTokenSequence(("أ", "\n", "ب", "\\n", "ج", "[PAR]", "د"))

        alignment = build_first_subtoken_alignment(
            tokenizer,
            original_tokens,
            max_length=512,
            stride=64,
        )

        self.assertEqual(
            tokenizer.calls[0]["tokens"],
            ("أ", "[PAR]", "ب", "[PAR]", "ج", "[PAR]", "د"),
        )
        self.assertEqual(
            alignment.original_tokens.tokens,
            ("أ", "\n", "ب", "\\n", "ج", "[PAR]", "د"),
        )
        self.assertEqual(len(tokenizer.calls[0]["tokens"]), original_tokens.token_count)
        self.assertEqual(alignment.windows[0].original_token_indexes, (0, 1, 2, 3, 4, 5, 6))
        self.assertEqual(alignment.windows[0].encoded_positions, (1, 2, 3, 4, 5, 6, 7))

    def test_unrecognized_paragraph_aliases_remain_unchanged_for_model_input(self) -> None:
        unchanged_tokens = (
            " ",
            "  ",
            "\t",
            "<PAR>",
            "[P]",
            "<P>",
            "PAR",
            "NEWLINE",
            "[NEWLINE]",
            "<NEWLINE>",
            "¶",
            "<br>",
            "<BR>",
            "/n",
            "\\\\n",
            ".",
            "؟",
            "?",
            "!",
            "…",
            "،",
            "كلمة",
        )
        tokenizer = _FakeTokenizer(_build_identity_encoding(len(unchanged_tokens)))

        build_first_subtoken_alignment(
            tokenizer,
            OriginalTokenSequence(unchanged_tokens),
            max_length=512,
            stride=64,
        )

        self.assertEqual(tokenizer.calls[0]["tokens"], unchanged_tokens)

    def test_non_fast_tokenizer_is_rejected(self) -> None:
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[[101, 11, 102]],
                word_ids_by_window=[[None, 0, None]],
            ),
            is_fast=False,
        )

        with self.assertRaises(UnsupportedTokenizerBehaviorError):
            build_first_subtoken_alignment(
                tokenizer,
                OriginalTokenSequence(("هذا",)),
                max_length=512,
                stride=64,
            )

    def test_none_word_ids_are_ignored_and_first_subtoken_is_selected(self) -> None:
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[[101, 21, 22, 31, 32, 102]],
                word_ids_by_window=[[None, 0, 0, 1, 1, None]],
            )
        )

        alignment = build_first_subtoken_alignment(
            tokenizer,
            OriginalTokenSequence(("الأول", "الثاني")),
            max_length=512,
            stride=64,
        )

        self.assertEqual(alignment.window_count, 1)
        self.assertEqual(alignment.windows[0].original_token_indexes, (0, 1))
        self.assertEqual(alignment.windows[0].encoded_positions, (1, 3))

    def test_same_original_token_can_be_observed_in_multiple_windows(self) -> None:
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[
                    [101, 11, 12, 13, 102],
                    [101, 13, 14, 15, 102],
                ],
                word_ids_by_window=[
                    [None, 0, 1, 2, None],
                    [None, 2, 3, 4, None],
                ],
            )
        )

        alignment = build_first_subtoken_alignment(
            tokenizer,
            OriginalTokenSequence(("t0", "t1", "t2", "t3", "t4")),
            max_length=512,
            stride=64,
        )

        self.assertEqual(alignment.windows[0].original_token_indexes, (0, 1, 2))
        self.assertEqual(alignment.windows[1].original_token_indexes, (2, 3, 4))

    def test_out_of_range_word_id_is_rejected(self) -> None:
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[[101, 11, 102]],
                word_ids_by_window=[[None, 2, None]],
            )
        )

        with self.assertRaises(InvalidWordIdError):
            build_first_subtoken_alignment(
                tokenizer,
                OriginalTokenSequence(("هذا",)),
                max_length=512,
                stride=64,
            )

    def test_negative_word_id_is_rejected(self) -> None:
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[[101, 11, 102]],
                word_ids_by_window=[[None, -1, None]],
            )
        )

        with self.assertRaises(InvalidWordIdError):
            build_first_subtoken_alignment(
                tokenizer,
                OriginalTokenSequence(("هذا",)),
                max_length=512,
                stride=64,
            )

    def test_token_with_zero_observations_is_rejected(self) -> None:
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[[101, 11, 102]],
                word_ids_by_window=[[None, 0, None]],
            )
        )

        with self.assertRaises(MissingTokenObservationError):
            build_first_subtoken_alignment(
                tokenizer,
                OriginalTokenSequence(("هذا", "نص")),
                max_length=512,
                stride=64,
            )

    def test_token_order_and_count_remain_unchanged(self) -> None:
        original_tokens = OriginalTokenSequence(("الأول", "الثاني", "الثالث"))
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[[101, 11, 21, 31, 102]],
                word_ids_by_window=[[None, 0, 1, 2, None]],
            )
        )

        alignment = build_first_subtoken_alignment(
            tokenizer,
            original_tokens,
            max_length=512,
            stride=64,
        )

        self.assertEqual(alignment.original_tokens.tokens, original_tokens.tokens)
        self.assertEqual(alignment.windows[0].original_token_indexes, (0, 1, 2))


class _FakeBatchEncoding(dict):
    def __init__(
        self,
        *,
        input_ids_rows: list[list[int]],
        word_ids_by_window: list[list[int | None]],
    ) -> None:
        super().__init__(
            {
                "input_ids": torch.tensor(input_ids_rows, dtype=torch.long),
                "attention_mask": torch.ones(
                    (len(input_ids_rows), len(input_ids_rows[0])),
                    dtype=torch.long,
                ),
            }
        )
        self._word_ids_by_window = [list(word_ids) for word_ids in word_ids_by_window]

    def word_ids(self, batch_index: int) -> list[int | None]:
        return list(self._word_ids_by_window[batch_index])


class _FakeTokenizer:
    def __init__(self, encoding: _FakeBatchEncoding, *, is_fast: bool = True) -> None:
        self._encoding = encoding
        self.is_fast = is_fast
        self.calls: list[dict[str, object]] = []

    def __call__(self, tokens: list[str], **kwargs) -> _FakeBatchEncoding:
        self.calls.append({"tokens": tuple(tokens), "kwargs": kwargs})
        return self._encoding


def _build_identity_encoding(token_count: int) -> _FakeBatchEncoding:
    input_ids = [[101, *range(11, 11 + token_count), 102]]
    word_ids = [[None, *range(token_count), None]]
    return _FakeBatchEncoding(
        input_ids_rows=input_ids,
        word_ids_by_window=word_ids,
    )


if __name__ == "__main__":
    unittest.main()
