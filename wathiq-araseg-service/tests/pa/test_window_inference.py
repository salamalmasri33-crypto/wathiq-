from __future__ import annotations

import math
from pathlib import Path
import sys
import time
import types
import unittest

import torch

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.pa import (  # noqa: E402
    NonFiniteModelOutputError,
    OriginalTokenSequence,
    PAEnsembleWindowInferenceEngine,
    PA_BASE_WEIGHT,
    PA_MICRO_WEIGHT,
    ProbabilityShapeMismatchError,
    TokenizerModelCompatibilityError,
)


class PAWindowInferenceUnitTests(unittest.TestCase):
    def test_inference_preserves_actual_newline_token_in_result(self) -> None:
        sequence = OriginalTokenSequence(("قبل", "\n", "بعد"))
        tokenizer = _FakeTokenizer(_build_identity_encoding(3))
        base_model = _DeterministicFakeModel(
            {
                (101, 11, 12, 13, 102): _build_logits(5, {1: 0.2, 2: 0.4, 3: 0.6}),
            }
        )
        micro_model = _DeterministicFakeModel(
            {
                (101, 11, 12, 13, 102): _build_logits(5, {1: 0.3, 2: 0.5, 3: 0.7}),
            }
        )

        result = PAEnsembleWindowInferenceEngine(
            tokenizer,
            base_model,
            micro_model,
        ).infer_probabilities(sequence)

        self.assertEqual(tokenizer.calls[0]["tokens"], ("قبل", "[PAR]", "بعد"))
        self.assertEqual(result.original_tokens.tokens, ("قبل", "\n", "بعد"))
        self.assertEqual(result.token_probabilities[1].token, "\n")

    def test_inference_preserves_literal_backslash_n_token_in_result(self) -> None:
        sequence = OriginalTokenSequence(("قبل", "\\n", "بعد"))
        tokenizer = _FakeTokenizer(_build_identity_encoding(3))
        base_model = _DeterministicFakeModel(
            {
                (101, 11, 12, 13, 102): _build_logits(5, {1: 0.2, 2: 0.4, 3: 0.6}),
            }
        )
        micro_model = _DeterministicFakeModel(
            {
                (101, 11, 12, 13, 102): _build_logits(5, {1: 0.3, 2: 0.5, 3: 0.7}),
            }
        )

        result = PAEnsembleWindowInferenceEngine(
            tokenizer,
            base_model,
            micro_model,
        ).infer_probabilities(sequence)

        self.assertEqual(tokenizer.calls[0]["tokens"], ("قبل", "[PAR]", "بعد"))
        self.assertEqual(result.original_tokens.tokens, ("قبل", "\\n", "بعد"))
        self.assertEqual(result.token_probabilities[1].token, "\\n")

    def test_inference_preserves_existing_par_token_in_result(self) -> None:
        sequence = OriginalTokenSequence(("قبل", "[PAR]", "بعد"))
        tokenizer = _FakeTokenizer(_build_identity_encoding(3))
        base_model = _DeterministicFakeModel(
            {
                (101, 11, 12, 13, 102): _build_logits(5, {1: 0.2, 2: 0.4, 3: 0.6}),
            }
        )
        micro_model = _DeterministicFakeModel(
            {
                (101, 11, 12, 13, 102): _build_logits(5, {1: 0.3, 2: 0.5, 3: 0.7}),
            }
        )

        result = PAEnsembleWindowInferenceEngine(
            tokenizer,
            base_model,
            micro_model,
        ).infer_probabilities(sequence)

        self.assertEqual(tokenizer.calls[0]["tokens"], ("قبل", "[PAR]", "بعد"))
        self.assertEqual(result.original_tokens.tokens, ("قبل", "[PAR]", "بعد"))
        self.assertEqual(result.token_probabilities[1].token, "[PAR]")

    def test_inference_uses_shared_mapped_tokenization_for_both_models(self) -> None:
        sequence = OriginalTokenSequence(("أ", "\n", "ب", "\\n", "ج", "[PAR]", "د"))
        tokenizer = _FakeTokenizer(_build_identity_encoding(7))
        base_model = _DeterministicFakeModel(
            {
                (101, 11, 12, 13, 14, 15, 16, 17, 102): _build_logits(
                    9,
                    {1: 0.1, 2: 0.2, 3: 0.3, 4: 0.4, 5: 0.5, 6: 0.6, 7: 0.7},
                ),
            }
        )
        micro_model = _DeterministicFakeModel(
            {
                (101, 11, 12, 13, 14, 15, 16, 17, 102): _build_logits(
                    9,
                    {1: 0.15, 2: 0.25, 3: 0.35, 4: 0.45, 5: 0.55, 6: 0.65, 7: 0.75},
                ),
            }
        )

        result = PAEnsembleWindowInferenceEngine(
            tokenizer,
            base_model,
            micro_model,
        ).infer_probabilities(sequence)

        self.assertEqual(len(tokenizer.calls), 1)
        self.assertEqual(
            tokenizer.calls[0]["tokens"],
            ("أ", "[PAR]", "ب", "[PAR]", "ج", "[PAR]", "د"),
        )
        self.assertEqual(base_model.seen_input_id_windows, micro_model.seen_input_id_windows)
        self.assertEqual(base_model.seen_attention_masks, micro_model.seen_attention_masks)
        self.assertEqual(result.original_tokens.tokens, sequence.tokens)
        self.assertEqual(
            tuple(record.token for record in result.token_probabilities),
            sequence.tokens,
        )
        self.assertEqual(len(result.token_probabilities), sequence.token_count)

    def test_class_one_softmax_probability_is_selected(self) -> None:
        sequence = OriginalTokenSequence(("هذا",))
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[[101, 11, 102]],
                word_ids_by_window=[[None, 0, None]],
            )
        )
        base_model = _DeterministicFakeModel(
            {
                (101, 11, 102): _build_logits(3, {1: 0.8}),
            }
        )
        micro_model = _DeterministicFakeModel(
            {
                (101, 11, 102): _build_logits(3, {1: 0.4}),
            }
        )
        engine = PAEnsembleWindowInferenceEngine(tokenizer, base_model, micro_model)

        result = engine.infer_probabilities(sequence)

        self.assertAlmostEqual(result.token_probabilities[0].base_probability, 0.8, places=12)
        self.assertAlmostEqual(result.token_probabilities[0].micro_probability, 0.4, places=12)
        self.assertAlmostEqual(
            result.token_probabilities[0].blended_probability,
            (PA_BASE_WEIGHT * 0.8) + (PA_MICRO_WEIGHT * 0.4),
            places=12,
        )

    def test_probabilities_not_logits_are_averaged(self) -> None:
        sequence = OriginalTokenSequence(("هذا",))
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[
                    [101, 11, 102],
                    [101, 12, 102],
                ],
                word_ids_by_window=[
                    [None, 0, None],
                    [None, 0, None],
                ],
            )
        )
        base_model = _DeterministicFakeModel(
            {
                (101, 11, 102): _build_logits(3, {1: 0.1}),
                (101, 12, 102): _build_logits(3, {1: 0.6}),
            }
        )
        micro_model = _DeterministicFakeModel(
            {
                (101, 11, 102): _build_logits(3, {1: 0.2}),
                (101, 12, 102): _build_logits(3, {1: 0.4}),
            }
        )
        engine = PAEnsembleWindowInferenceEngine(tokenizer, base_model, micro_model)

        result = engine.infer_probabilities(sequence)

        self.assertAlmostEqual(result.token_probabilities[0].base_probability, 0.35, places=12)
        self.assertAlmostEqual(result.token_probabilities[0].micro_probability, 0.3, places=12)

    def test_base_and_micro_probabilities_are_computed_independently(self) -> None:
        sequence = OriginalTokenSequence(("هذا",))
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[[101, 11, 102]],
                word_ids_by_window=[[None, 0, None]],
            )
        )
        base_model = _DeterministicFakeModel(
            {
                (101, 11, 102): _build_logits(3, {1: 0.9}),
            }
        )
        micro_model = _DeterministicFakeModel(
            {
                (101, 11, 102): _build_logits(3, {1: 0.2}),
            }
        )

        result = PAEnsembleWindowInferenceEngine(
            tokenizer,
            base_model,
            micro_model,
        ).infer_probabilities(sequence)

        self.assertAlmostEqual(result.token_probabilities[0].base_probability, 0.9, places=12)
        self.assertAlmostEqual(result.token_probabilities[0].micro_probability, 0.2, places=12)
        self.assertEqual(result.token_probabilities[0].base_observation_count, 1)
        self.assertEqual(result.token_probabilities[0].micro_observation_count, 1)

    def test_wrong_label_dimension_is_rejected(self) -> None:
        sequence = OriginalTokenSequence(("هذا",))
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[[101, 11, 102]],
                word_ids_by_window=[[None, 0, None]],
            )
        )
        base_model = _DeterministicFakeModel(
            {
                (101, 11, 102): _build_logits(3, {1: 0.5}, label_count=3),
            },
            num_labels=2,
        )
        micro_model = _DeterministicFakeModel(
            {
                (101, 11, 102): _build_logits(3, {1: 0.5}),
            }
        )

        with self.assertRaises(ProbabilityShapeMismatchError):
            PAEnsembleWindowInferenceEngine(
                tokenizer,
                base_model,
                micro_model,
            ).infer_probabilities(sequence)

    def test_wrong_output_rank_is_rejected(self) -> None:
        sequence = OriginalTokenSequence(("هذا",))
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[[101, 11, 102]],
                word_ids_by_window=[[None, 0, None]],
            )
        )
        base_model = _DeterministicFakeModel(
            {
                (101, 11, 102): torch.zeros((3, 2), dtype=torch.float64),
            }
        )
        micro_model = _DeterministicFakeModel(
            {
                (101, 11, 102): _build_logits(3, {1: 0.5}),
            }
        )

        with self.assertRaises(ProbabilityShapeMismatchError):
            PAEnsembleWindowInferenceEngine(
                tokenizer,
                base_model,
                micro_model,
            ).infer_probabilities(sequence)

    def test_non_finite_logits_are_rejected(self) -> None:
        sequence = OriginalTokenSequence(("هذا",))
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[[101, 11, 102]],
                word_ids_by_window=[[None, 0, None]],
            )
        )
        bad_logits = _build_logits(3, {1: 0.5})
        bad_logits[0, 1, 1] = float("nan")
        base_model = _DeterministicFakeModel({(101, 11, 102): bad_logits})
        micro_model = _DeterministicFakeModel(
            {
                (101, 11, 102): _build_logits(3, {1: 0.5}),
            }
        )

        with self.assertRaises(NonFiniteModelOutputError):
            PAEnsembleWindowInferenceEngine(
                tokenizer,
                base_model,
                micro_model,
            ).infer_probabilities(sequence)

    def test_long_overlap_aggregation_preserves_one_record_per_token_and_order(self) -> None:
        sequence = OriginalTokenSequence(("t0", "t1", "t2", "t3"))
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[
                    [101, 11, 12, 13, 102],
                    [101, 13, 14, 15, 102],
                ],
                word_ids_by_window=[
                    [None, 0, 1, 2, None],
                    [None, 1, 2, 3, None],
                ],
            )
        )
        base_model = _DeterministicFakeModel(
            {
                (101, 11, 12, 13, 102): _build_logits(5, {1: 0.1, 2: 0.2, 3: 0.3}),
                (101, 13, 14, 15, 102): _build_logits(5, {1: 0.4, 2: 0.5, 3: 0.6}),
            }
        )
        micro_model = _DeterministicFakeModel(
            {
                (101, 11, 12, 13, 102): _build_logits(5, {1: 0.2, 2: 0.3, 3: 0.4}),
                (101, 13, 14, 15, 102): _build_logits(5, {1: 0.5, 2: 0.6, 3: 0.7}),
            }
        )
        engine = PAEnsembleWindowInferenceEngine(tokenizer, base_model, micro_model)

        result = engine.infer_probabilities(sequence)

        self.assertEqual(result.window_count, 2)
        self.assertEqual(len(result.token_probabilities), 4)
        self.assertEqual(
            tuple(record.token for record in result.token_probabilities),
            ("t0", "t1", "t2", "t3"),
        )
        self.assertEqual(
            tuple(record.base_observation_count for record in result.token_probabilities),
            (1, 2, 2, 1),
        )
        self.assertEqual(
            tuple(record.micro_observation_count for record in result.token_probabilities),
            (1, 2, 2, 1),
        )
        self.assertAlmostEqual(result.token_probabilities[1].base_probability, 0.3, places=12)
        self.assertAlmostEqual(result.token_probabilities[2].base_probability, 0.4, places=12)

    def test_deterministic_inference_repeats_identically(self) -> None:
        sequence = OriginalTokenSequence(("أ", "\n", "ب", "\\n", "ج", "[PAR]", "د"))
        tokenizer = _FakeTokenizer(_build_identity_encoding(7))
        base_model = _DeterministicFakeModel(
            {
                (101, 11, 12, 13, 14, 15, 16, 17, 102): _build_logits(
                    9,
                    {1: 0.2, 2: 0.3, 3: 0.4, 4: 0.5, 5: 0.6, 6: 0.7, 7: 0.8},
                ),
            }
        )
        micro_model = _DeterministicFakeModel(
            {
                (101, 11, 12, 13, 14, 15, 16, 17, 102): _build_logits(
                    9,
                    {1: 0.15, 2: 0.25, 3: 0.35, 4: 0.45, 5: 0.55, 6: 0.65, 7: 0.75},
                ),
            }
        )
        engine = PAEnsembleWindowInferenceEngine(tokenizer, base_model, micro_model)

        first = engine.infer_probabilities(sequence)
        second = engine.infer_probabilities(sequence)

        self.assertEqual(first, second)

    def test_tokenizer_and_model_vocabulary_mismatch_is_rejected(self) -> None:
        tokenizer = _FakeTokenizer(
            _FakeBatchEncoding(
                input_ids_rows=[[101, 11, 102]],
                word_ids_by_window=[[None, 0, None]],
            ),
            vocab_size=30001,
        )
        base_model = _DeterministicFakeModel(
            {(101, 11, 102): _build_logits(3, {1: 0.5})},
            vocab_size=30002,
        )
        micro_model = _DeterministicFakeModel(
            {(101, 11, 102): _build_logits(3, {1: 0.5})},
        )

        with self.assertRaises(TokenizerModelCompatibilityError):
            PAEnsembleWindowInferenceEngine(tokenizer, base_model, micro_model)


class PARealModelIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._base_dir = SERVICE_ROOT / "models" / "pa" / "best_model"
        cls._micro_dir = SERVICE_ROOT / "models" / "pa" / "micro" / "best_model"

        if not cls._base_dir.is_dir() or not cls._micro_dir.is_dir():
            raise unittest.SkipTest("Local PA base or micro best_model directory is not present.")

        try:
            from transformers import AutoModelForTokenClassification, AutoTokenizer
        except ImportError as exc:
            raise unittest.SkipTest("Transformers is not installed locally.") from exc

        cls.raw_tokenizer = AutoTokenizer.from_pretrained(
            str(cls._base_dir),
            local_files_only=True,
            use_fast=True,
            trust_remote_code=False,
        )
        cls.raw_base_model = AutoModelForTokenClassification.from_pretrained(
            str(cls._base_dir),
            local_files_only=True,
            trust_remote_code=False,
        )
        cls.raw_micro_model = AutoModelForTokenClassification.from_pretrained(
            str(cls._micro_dir),
            local_files_only=True,
            trust_remote_code=False,
        )

    def test_real_pa_ensemble_inference_runs_offline_on_small_input(self) -> None:
        sequence = OriginalTokenSequence(
            ("هذا", "\n", "نص", "\\n", "عربي", "[PAR]", ".", "؟")
        )
        first_tokenizer, first_base_model, first_micro_model, first_engine = (
            self._build_recording_engine()
        )
        second_tokenizer, second_base_model, second_micro_model, second_engine = (
            self._build_recording_engine()
        )

        first = first_engine.infer_probabilities(sequence)
        second = second_engine.infer_probabilities(sequence)

        self._assert_probability_result_is_valid(first, expected_window_count=1)
        self._assert_results_match(first, second)
        self.assertEqual(
            first_tokenizer.calls[0]["tokens"],
            ("هذا", "[PAR]", "نص", "[PAR]", "عربي", "[PAR]", ".", "؟"),
        )
        self.assertEqual(
            second_tokenizer.calls[0]["tokens"],
            ("هذا", "[PAR]", "نص", "[PAR]", "عربي", "[PAR]", ".", "؟"),
        )
        self.assertEqual(first.original_tokens.tokens, sequence.tokens)
        self.assertEqual(
            tuple(record.token for record in first.token_probabilities),
            sequence.tokens,
        )
        self.assertEqual(
            first_base_model.seen_input_id_windows,
            first_micro_model.seen_input_id_windows,
        )
        self.assertEqual(
            second_base_model.seen_input_id_windows,
            second_micro_model.seen_input_id_windows,
        )
        self.assertFalse(first_base_model.training)
        self.assertFalse(first_micro_model.training)
        self.assertFalse(second_base_model.training)
        self.assertFalse(second_micro_model.training)

    def test_real_pa_ensemble_inference_aggregates_multiple_windows(self) -> None:
        long_tokens = OriginalTokenSequence(tuple(["هذا", "نص", "،", "."] * 160))
        _tokenizer, base_model, micro_model, engine = self._build_recording_engine()

        start_time = time.perf_counter()
        result = engine.infer_probabilities(long_tokens)
        duration_seconds = time.perf_counter() - start_time

        self._assert_probability_result_is_valid(result, expected_window_count=None)
        self.assertGreater(result.window_count, 1)
        self.assertGreater(duration_seconds, 0.0)
        self.assertEqual(base_model.seen_input_id_windows, micro_model.seen_input_id_windows)
        self.assertFalse(base_model.training)
        self.assertFalse(micro_model.training)

    def _build_recording_engine(self):
        tokenizer = _RecordingTokenizer(self.raw_tokenizer)
        base_model = _RecordingModelProxy(self.raw_base_model)
        micro_model = _RecordingModelProxy(self.raw_micro_model)
        engine = PAEnsembleWindowInferenceEngine(tokenizer, base_model, micro_model)
        return tokenizer, base_model, micro_model, engine

    def _assert_probability_result_is_valid(
        self,
        result,
        *,
        expected_window_count: int | None,
    ) -> None:
        if expected_window_count is not None:
            self.assertEqual(result.window_count, expected_window_count)

        self.assertEqual(len(result.token_probabilities), result.original_tokens.token_count)
        for token_probability in result.token_probabilities:
            self.assertGreaterEqual(token_probability.base_probability, 0.0)
            self.assertLessEqual(token_probability.base_probability, 1.0)
            self.assertGreaterEqual(token_probability.micro_probability, 0.0)
            self.assertLessEqual(token_probability.micro_probability, 1.0)
            self.assertGreaterEqual(token_probability.blended_probability, 0.0)
            self.assertLessEqual(token_probability.blended_probability, 1.0)
            self.assertTrue(math.isfinite(token_probability.base_probability))
            self.assertTrue(math.isfinite(token_probability.micro_probability))
            self.assertTrue(math.isfinite(token_probability.blended_probability))
            self.assertGreaterEqual(token_probability.base_observation_count, 1)
            self.assertGreaterEqual(token_probability.micro_observation_count, 1)

    def _assert_results_match(self, first, second) -> None:
        self.assertEqual(first.original_tokens, second.original_tokens)
        self.assertEqual(first.window_count, second.window_count)
        self.assertEqual(first.max_length, second.max_length)
        self.assertEqual(first.stride, second.stride)
        self.assertEqual(len(first.token_probabilities), len(second.token_probabilities))

        for left, right in zip(first.token_probabilities, second.token_probabilities, strict=True):
            self.assertEqual(left.token_index, right.token_index)
            self.assertEqual(left.token, right.token)
            self.assertEqual(left.base_observation_count, right.base_observation_count)
            self.assertEqual(left.micro_observation_count, right.micro_observation_count)
            self.assertAlmostEqual(left.base_probability, right.base_probability, places=12)
            self.assertAlmostEqual(left.micro_probability, right.micro_probability, places=12)
            self.assertAlmostEqual(left.blended_probability, right.blended_probability, places=12)


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
    def __init__(
        self,
        encoding: _FakeBatchEncoding,
        *,
        is_fast: bool = True,
        vocab_size: int = 30001,
    ) -> None:
        self._encoding = encoding
        self.is_fast = is_fast
        self._vocab_size = vocab_size
        self.calls: list[dict[str, object]] = []

    def __len__(self) -> int:
        return self._vocab_size

    def __call__(self, tokens: list[str], **kwargs) -> _FakeBatchEncoding:
        self.calls.append({"tokens": tuple(tokens), "kwargs": kwargs})
        return self._encoding


class _DeterministicFakeModel:
    def __init__(
        self,
        logits_by_window: dict[tuple[int, ...], torch.Tensor],
        *,
        num_labels: int = 2,
        vocab_size: int = 30001,
    ) -> None:
        self._logits_by_window = {
            key: value.clone() if hasattr(value, "clone") else value
            for key, value in logits_by_window.items()
        }
        self.config = types.SimpleNamespace(num_labels=num_labels, vocab_size=vocab_size)
        self.training = True
        self.device = torch.device("cpu")
        self.seen_input_id_windows: list[tuple[int, ...]] = []
        self.seen_attention_masks: list[tuple[int, ...]] = []

    def parameters(self):
        yield torch.zeros(1, device=self.device)

    def eval(self) -> _DeterministicFakeModel:
        self.training = False
        return self

    def __call__(self, **kwargs) -> types.SimpleNamespace:
        key = tuple(int(value) for value in kwargs["input_ids"][0].tolist())
        self.seen_input_id_windows.append(key)
        if "attention_mask" in kwargs:
            self.seen_attention_masks.append(
                tuple(int(value) for value in kwargs["attention_mask"][0].tolist())
            )
        return types.SimpleNamespace(logits=self._logits_by_window[key].clone())


class _RecordingTokenizer:
    def __init__(self, wrapped) -> None:
        self._wrapped = wrapped
        self.is_fast = wrapped.is_fast
        self.calls: list[dict[str, object]] = []

    def __len__(self) -> int:
        return len(self._wrapped)

    def __call__(self, tokens: list[str], **kwargs):
        self.calls.append({"tokens": tuple(tokens), "kwargs": kwargs})
        return self._wrapped(tokens, **kwargs)


class _RecordingModelProxy:
    def __init__(self, wrapped) -> None:
        self._wrapped = wrapped
        self.config = wrapped.config
        self.seen_input_id_windows: list[tuple[int, ...]] = []
        self.seen_attention_masks: list[tuple[int, ...]] = []

    @property
    def training(self) -> bool:
        return self._wrapped.training

    def parameters(self):
        return self._wrapped.parameters()

    def eval(self) -> _RecordingModelProxy:
        self._wrapped.eval()
        return self

    def __call__(self, **kwargs):
        self.seen_input_id_windows.append(
            tuple(int(value) for value in kwargs["input_ids"][0].tolist())
        )
        if "attention_mask" in kwargs:
            self.seen_attention_masks.append(
                tuple(int(value) for value in kwargs["attention_mask"][0].tolist())
            )
        return self._wrapped(**kwargs)

    def __getattr__(self, name: str):
        return getattr(self._wrapped, name)


def _build_logits(
    sequence_length: int,
    class_one_probabilities_by_position: dict[int, float],
    *,
    label_count: int = 2,
) -> torch.Tensor:
    logits = torch.zeros((1, sequence_length, label_count), dtype=torch.float64)
    for position, probability in class_one_probabilities_by_position.items():
        logits[0, position, 1] = math.log(probability / (1.0 - probability))
    return logits


def _build_identity_encoding(token_count: int) -> _FakeBatchEncoding:
    input_ids = [[101, *range(11, 11 + token_count), 102]]
    word_ids = [[None, *range(token_count), None]]
    return _FakeBatchEncoding(
        input_ids_rows=input_ids,
        word_ids_by_window=word_ids,
    )


if __name__ == "__main__":
    unittest.main()
