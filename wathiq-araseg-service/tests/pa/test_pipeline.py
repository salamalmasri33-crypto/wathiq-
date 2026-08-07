from __future__ import annotations

import inspect
from pathlib import Path
import sys
import time
import unittest
from unittest import mock

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.pa import (  # noqa: E402
    InvalidInferenceDependencyError,
    OriginalTokenSequence,
    PAEnsembleWindowInferenceEngine,
    PAPipeline,
    PAProbabilityResult,
    TokenProbability,
)
from wathiq_araseg.pa.exceptions import (  # noqa: E402
    InvalidPAProbabilityResultError,
    InvalidProbabilityValueError,
    MissingFinalBoundaryError,
    TokenCountMismatchError,
    TokenIndexMismatchError,
    TokenTextMismatchError,
    TokenizerModelCompatibilityError,
)
from wathiq_araseg.pa.postprocessing import (  # noqa: E402
    DEFAULT_THRESHOLD,
    PARAGRAPH_MARKERS,
    PUNCTUATION_THRESHOLD,
    BoundaryDecisionReason,
    PAPostProcessingResult,
    SentenceTokenGroup,
    TokenBoundaryDecision,
    postprocess_pa_probabilities,
)
from wathiq_araseg.pa import pipeline as pa_pipeline_module  # noqa: E402
from wathiq_araseg.segmentation import (  # noqa: E402
    AbstractSegmentationPipeline,
    InvalidSegmentationInputError,
    InvalidSegmentationResultError,
    SegmentationRequest,
    SegmentationToken,
    SourceSegmentReconstructionError,
    render_segments_from_token_boundaries,
)


class PAPipelineInterfaceTests(unittest.TestCase):
    def test_pipeline_implements_existing_abstraction_with_stable_identity(self) -> None:
        pipeline = PAPipeline(_RecordingInferenceEngine(_build_probability_result(("أ",), (0.1,))))

        self.assertIsInstance(pipeline, AbstractSegmentationPipeline)
        self.assertEqual(pipeline.track, "PA")
        self.assertEqual(pipeline.pipeline_id, "pa-current-micro-ensemble-861752")
        self.assertIs(PAPipeline.segment, AbstractSegmentationPipeline.segment)

        public_runtime_members = {
            name
            for name, value in PAPipeline.__dict__.items()
            if not name.startswith("_") and (callable(value) or isinstance(value, property))
        }
        self.assertEqual(public_runtime_members, {"track", "pipeline_id"})

    def test_constructor_requires_callable_inference_dependency(self) -> None:
        with self.assertRaises(InvalidInferenceDependencyError):
            PAPipeline(object())

    def test_pipeline_source_contains_no_duplicate_runtime_logic(self) -> None:
        source = inspect.getsource(pa_pipeline_module)

        for forbidden_snippet in (
            "softmax",
            "torch",
            "from_pretrained",
            "best_model",
            "0.543",
            "0.310",
            "PUNCTUATION_TOKENS",
            "PARAGRAPH_MARKERS",
            "force_last",
            "split(",
            "splitlines(",
            "re.",
            "tokenizer(",
            "search(",
            "\" \".join",
        ):
            with self.subTest(forbidden_snippet=forbidden_snippet):
                self.assertNotIn(forbidden_snippet, source)


class PAPipelineUnitTests(unittest.TestCase):
    def test_missing_token_input_is_rejected_without_fallback(self) -> None:
        engine = _RecordingInferenceEngine(_build_probability_result(("أ",), (0.1,)))
        pipeline = PAPipeline(engine)

        with self.assertRaises(InvalidSegmentationInputError):
            pipeline.segment(
                SegmentationRequest(
                    document_id="doc-raw",
                    text="أ ب",
                    track="PA",
                )
            )

        self.assertEqual(engine.calls, [])

    def test_pipeline_passes_exact_request_tokens_into_original_token_sequence(self) -> None:
        request = _build_rich_tokenized_request()
        expected_token_texts = tuple(token.text for token in request.tokens or ())
        engine = _RecordingInferenceEngine(
            _build_probability_result(
                expected_token_texts,
                (0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1),
            )
        )
        pipeline = PAPipeline(engine)

        pipeline.segment(request)

        self.assertEqual(engine.call_count, 1)
        self.assertEqual(len(engine.calls), 1)
        self.assertIsInstance(engine.calls[0], OriginalTokenSequence)
        self.assertEqual(engine.calls[0].tokens, expected_token_texts)

    def test_pipeline_uses_exact_orchestration_order_once_per_stage(self) -> None:
        request = _build_simple_tokenized_request()
        probability_result = _build_probability_result(("أ", "ب"), (0.1, 0.1))
        postprocessing_result = _build_postprocessing_result(("أ", "ب"), (1,))
        engine = _RecordingInferenceEngine(probability_result)
        pipeline = PAPipeline(engine)
        call_order: list[str] = []

        def fake_postprocess(actual_probability_result: PAProbabilityResult) -> PAPostProcessingResult:
            call_order.append("postprocess")
            self.assertIs(actual_probability_result, probability_result)
            return postprocessing_result

        def fake_render(
            *,
            normalized_text: str,
            tokens: tuple[SegmentationToken, ...],
            boundary_token_indices: tuple[int, ...],
        ) -> tuple[str, ...]:
            call_order.append("render")
            self.assertEqual(normalized_text, "أ ب")
            self.assertEqual(tuple(token.text for token in tokens), ("أ", "ب"))
            self.assertEqual(boundary_token_indices, (1,))
            return ("أ ب",)

        original_infer = engine.infer_probabilities

        def recording_infer(original_tokens: OriginalTokenSequence) -> PAProbabilityResult:
            call_order.append("inference")
            return original_infer(original_tokens)

        engine.infer_probabilities = recording_infer

        with (
            mock.patch.object(
                pa_pipeline_module,
                "postprocess_pa_probabilities",
                side_effect=fake_postprocess,
            ),
            mock.patch.object(
                pa_pipeline_module,
                "render_segments_from_token_boundaries",
                side_effect=fake_render,
            ),
        ):
            result = pipeline.segment(request)

        self.assertEqual(call_order, ["inference", "postprocess", "render"])
        self.assertEqual(tuple(segment.text for segment in result.segments), ("أ ب",))

    def test_pipeline_preserves_exact_source_slices_and_gap_assignment(self) -> None:
        request = _build_rich_tokenized_request()
        engine = _RecordingInferenceEngine(
            _build_probability_result(
                tuple(token.text for token in request.tokens or ()),
                (0.6, 0.4, 0.1, 0.9, 0.1, 0.8, 0.2),
            )
        )
        pipeline = PAPipeline(engine)

        result = pipeline.segment(request)

        self.assertEqual(result.document_id, "doc-rich")
        self.assertEqual(result.track, "PA")
        self.assertEqual(result.pipeline_id, "pa-current-micro-ensemble-861752")
        self.assertEqual(result.normalized_text, request.text)
        self.assertEqual(
            tuple(segment.text for segment in result.segments),
            ("  أ", "  .", "\tب", "\n", "\\n", "[PAR]!  "),
        )
        self.assertEqual(
            "".join(segment.text for segment in result.segments),
            request.text,
        )

    def test_pipeline_uses_blended_probability_only_via_committed_postprocessing(self) -> None:
        request = _build_simple_tokenized_request()
        probability_result = _build_probability_result(
            ("أ", "ب"),
            (0.2, 0.1),
            base_probabilities=(0.95, 0.1),
            micro_probabilities=(0.95, 0.1),
        )
        engine = _RecordingInferenceEngine(probability_result)
        pipeline = PAPipeline(engine)

        result = pipeline.segment(request)
        direct_postprocessing = postprocess_pa_probabilities(probability_result)

        self.assertFalse(direct_postprocessing.decisions[0].is_boundary)
        self.assertEqual(tuple(segment.text for segment in result.segments), ("أ ب",))

    def test_probability_result_token_drift_is_rejected(self) -> None:
        request = _build_simple_tokenized_request()
        expected_tokens = tuple(token.text for token in request.tokens or ())
        invalid_results = (
            _make_invalid_probability_result(
                original_tokens=OriginalTokenSequence(expected_tokens),
                token_probabilities=(
                    _make_valid_token_probability(0, "أ", 0.2),
                ),
            ),
            _make_invalid_probability_result(
                original_tokens=OriginalTokenSequence(expected_tokens),
                token_probabilities=(
                    _make_valid_token_probability(0, "ب", 0.2),
                    _make_valid_token_probability(1, "أ", 0.1),
                ),
            ),
            _make_invalid_probability_result(
                original_tokens=OriginalTokenSequence(("ب", "أ")),
                token_probabilities=(
                    _make_valid_token_probability(0, "ب", 0.2),
                    _make_valid_token_probability(1, "أ", 0.1),
                ),
            ),
        )

        for invalid_result in invalid_results:
            with self.subTest(invalid_result=invalid_result):
                pipeline = PAPipeline(_RecordingInferenceEngine(invalid_result))

                with self.assertRaises(InvalidSegmentationResultError) as raised:
                    pipeline.segment(request)

                self.assertIsInstance(
                    raised.exception.__cause__,
                    (TokenCountMismatchError, TokenTextMismatchError),
                )

    def test_postprocessing_result_token_drift_and_missing_final_boundary_are_rejected(self) -> None:
        request = _build_simple_tokenized_request()
        probability_result = _build_probability_result(("أ", "ب"), (0.2, 0.1))
        engine = _RecordingInferenceEngine(probability_result)
        pipeline = PAPipeline(engine)
        invalid_results = (
            _make_invalid_postprocessing_result(
                original_tokens=("ب", "أ"),
                decisions=(
                    _make_decision(0, "ب", 0.2, True, BoundaryDecisionReason.DEFAULT_THRESHOLD),
                    _make_decision(1, "أ", 0.1, True, BoundaryDecisionReason.FORCE_LAST),
                ),
                sentence_groups=(
                    _make_group(0, 0, 0, ("ب",), BoundaryDecisionReason.DEFAULT_THRESHOLD),
                    _make_group(1, 1, 1, ("أ",), BoundaryDecisionReason.FORCE_LAST),
                ),
            ),
            _make_invalid_postprocessing_result(
                original_tokens=("أ", "ب"),
                decisions=(
                    _make_decision(0, "أ", 0.2, False, BoundaryDecisionReason.DEFAULT_THRESHOLD),
                    _make_decision(1, "ب", 0.1, False, BoundaryDecisionReason.DEFAULT_THRESHOLD),
                ),
                sentence_groups=(
                    _make_group(0, 0, 1, ("أ", "ب"), BoundaryDecisionReason.DEFAULT_THRESHOLD),
                ),
            ),
        )

        for invalid_result in invalid_results:
            with self.subTest(invalid_result=invalid_result):
                with mock.patch.object(
                    pa_pipeline_module,
                    "postprocess_pa_probabilities",
                    return_value=invalid_result,
                ):
                    with self.assertRaises(InvalidSegmentationResultError) as raised:
                        pipeline.segment(request)

                self.assertIsInstance(
                    raised.exception.__cause__,
                    (TokenTextMismatchError, MissingFinalBoundaryError),
                )

    def test_controlled_failures_are_not_swallowed_or_mislabeled(self) -> None:
        request = _build_simple_tokenized_request()

        pipeline = PAPipeline(
            _RecordingInferenceEngine(
                TokenizerModelCompatibilityError("incompatible model"),
            )
        )
        with self.assertRaises(InvalidSegmentationResultError) as inference_failure:
            pipeline.segment(request)
        self.assertIsInstance(
            inference_failure.exception.__cause__,
            TokenizerModelCompatibilityError,
        )

        pipeline = PAPipeline(
            _RecordingInferenceEngine(
                _make_invalid_probability_result(
                    original_tokens=OriginalTokenSequence(("أ", "ب")),
                    token_probabilities=(
                        _make_invalid_token_probability(
                            token_index=0,
                            token="أ",
                            blended_probability=float("nan"),
                        ),
                        _make_valid_token_probability(1, "ب", 0.1),
                    ),
                )
            )
        )
        with self.assertRaises(InvalidSegmentationResultError) as probability_failure:
            pipeline.segment(request)
        self.assertIsInstance(
            probability_failure.exception.__cause__,
            InvalidProbabilityValueError,
        )

        valid_pipeline = PAPipeline(
            _RecordingInferenceEngine(_build_probability_result(("أ", "ب"), (0.2, 0.1)))
        )
        with mock.patch.object(
            pa_pipeline_module,
            "render_segments_from_token_boundaries",
            side_effect=SourceSegmentReconstructionError("bad render"),
        ):
            with self.assertRaises(SourceSegmentReconstructionError):
                valid_pipeline.segment(request)

    def test_pipeline_is_deterministic_for_identical_tokenized_input(self) -> None:
        request = _build_rich_tokenized_request()
        probability_result = _build_probability_result(
            tuple(token.text for token in request.tokens or ()),
            (0.6, 0.4, 0.1, 0.9, 0.1, 0.8, 0.2),
        )
        pipeline = PAPipeline(_RecordingInferenceEngine(probability_result))

        first = pipeline.segment(request)
        second = pipeline.segment(request)

        self.assertEqual(first, second)


class PAPipelineRealIntegrationTests(unittest.TestCase):
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

        cls.tokenizer = AutoTokenizer.from_pretrained(
            str(cls._base_dir),
            local_files_only=True,
            use_fast=True,
            trust_remote_code=False,
        )
        cls.base_model = AutoModelForTokenClassification.from_pretrained(
            str(cls._base_dir),
            local_files_only=True,
            trust_remote_code=False,
        )
        cls.micro_model = AutoModelForTokenClassification.from_pretrained(
            str(cls._micro_dir),
            local_files_only=True,
            trust_remote_code=False,
        )

    def test_real_pipeline_matches_direct_reference_path_offline(self) -> None:
        engine = PAEnsembleWindowInferenceEngine(
            self.tokenizer,
            self.base_model,
            self.micro_model,
        )
        pipeline = PAPipeline(engine)
        request = _build_rich_tokenized_request(document_id="doc-real", track="PA")

        first = pipeline.segment(request)
        second = pipeline.segment(request)

        original_tokens = OriginalTokenSequence(tuple(token.text for token in request.tokens or ()))
        probability_result = engine.infer_probabilities(original_tokens)
        postprocessing_result = postprocess_pa_probabilities(probability_result)
        boundary_indices = tuple(
            decision.token_index
            for decision in postprocessing_result.decisions
            if decision.is_boundary
        )
        reference_segments = render_segments_from_token_boundaries(
            normalized_text=request.text,
            tokens=request.tokens or (),
            boundary_token_indices=boundary_indices,
        )

        self.assertFalse(self.base_model.training)
        self.assertFalse(self.micro_model.training)
        self.assertEqual(first, second)
        self.assertEqual(first.document_id, "doc-real")
        self.assertEqual(first.track, "PA")
        self.assertEqual(first.pipeline_id, "pa-current-micro-ensemble-861752")
        self.assertEqual(first.normalized_text, request.text)
        self.assertTrue(all(segment.text != "" for segment in first.segments))
        self.assertEqual(
            tuple(segment.text for segment in first.segments),
            reference_segments,
        )
        self.assertEqual("".join(segment.text for segment in first.segments), request.text)
        self.assertIn("\n", "".join(segment.text for segment in first.segments))
        self.assertIn("\\n", "".join(segment.text for segment in first.segments))
        self.assertIn("[PAR]", "".join(segment.text for segment in first.segments))


class _RecordingInferenceEngine:
    def __init__(self, response_or_exception) -> None:
        self._response_or_exception = response_or_exception
        self.calls: list[OriginalTokenSequence] = []
        self.call_count = 0

    def infer_probabilities(
        self,
        original_tokens: OriginalTokenSequence,
    ) -> PAProbabilityResult:
        self.calls.append(original_tokens)
        self.call_count += 1

        if isinstance(self._response_or_exception, Exception):
            raise self._response_or_exception

        return self._response_or_exception


def _build_simple_tokenized_request() -> SegmentationRequest:
    return SegmentationRequest(
        document_id="  doc-simple  ",
        text="أ ب",
        track=" pa ",
        tokens=(
            SegmentationToken(index=0, text="أ", start_offset=0, end_offset=1),
            SegmentationToken(index=1, text="ب", start_offset=2, end_offset=3),
        ),
    )


def _build_rich_tokenized_request(
    *,
    document_id: str = "  doc-rich  ",
    track: str = " pa ",
) -> SegmentationRequest:
    source = "  أ  .\tب\n\\n[PAR]!  "
    tokens = (
        SegmentationToken(index=0, text="أ", start_offset=2, end_offset=3),
        SegmentationToken(index=1, text=".", start_offset=5, end_offset=6),
        SegmentationToken(index=2, text="ب", start_offset=7, end_offset=8),
        SegmentationToken(index=3, text="\n", start_offset=8, end_offset=9),
        SegmentationToken(index=4, text="\\n", start_offset=9, end_offset=11),
        SegmentationToken(index=5, text="[PAR]", start_offset=11, end_offset=16),
        SegmentationToken(index=6, text="!", start_offset=16, end_offset=17),
    )

    return SegmentationRequest(
        document_id=document_id,
        text=source,
        track=track,
        tokens=tokens,
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


def _build_postprocessing_result(
    tokens: tuple[str, ...],
    boundary_indexes: tuple[int, ...],
) -> PAPostProcessingResult:
    boundary_set = set(boundary_indexes)
    decisions = tuple(
        _make_decision(
            index,
            token,
            0.9 if index in boundary_set else 0.1,
            index in boundary_set,
            BoundaryDecisionReason.FORCE_LAST
            if index == len(tokens) - 1 and index in boundary_set
            else BoundaryDecisionReason.DEFAULT_THRESHOLD,
        )
        for index, token in enumerate(tokens)
    )

    sentence_groups: list[SentenceTokenGroup] = []
    start_index = 0
    for decision in decisions:
        if not decision.is_boundary:
            continue

        sentence_groups.append(
            _make_group(
                len(sentence_groups),
                start_index,
                decision.token_index,
                tokens[start_index : decision.token_index + 1],
                decision.decision_reason,
            )
        )
        start_index = decision.token_index + 1

    return PAPostProcessingResult(
        original_tokens=tokens,
        decisions=decisions,
        sentence_groups=tuple(sentence_groups),
        default_threshold=DEFAULT_THRESHOLD,
        punctuation_threshold=PUNCTUATION_THRESHOLD,
        punctuation_tokens=(".", "؟", "?", "!", "…"),
        paragraph_markers=PARAGRAPH_MARKERS,
        paragraph_rule_enabled=True,
        force_last_enabled=True,
    )


def _make_decision(
    token_index: int,
    token: str,
    probability: float,
    is_boundary: bool,
    reason: BoundaryDecisionReason,
) -> TokenBoundaryDecision:
    return TokenBoundaryDecision(
        token_index=token_index,
        token=token,
        probability=probability,
        applied_threshold=PUNCTUATION_THRESHOLD
        if token in (".", "؟", "?", "!", "…")
        else DEFAULT_THRESHOLD,
        is_boundary=is_boundary,
        decision_reason=reason,
    )


def _make_group(
    sentence_index: int,
    start_token_index: int,
    end_token_index: int,
    tokens: tuple[str, ...],
    reason: BoundaryDecisionReason,
) -> SentenceTokenGroup:
    return SentenceTokenGroup(
        sentence_index=sentence_index,
        start_token_index=start_token_index,
        end_token_index=end_token_index,
        tokens=tokens,
        boundary_token_index=end_token_index,
        boundary_reason=reason,
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


def _make_invalid_postprocessing_result(
    *,
    original_tokens,
    decisions,
    sentence_groups,
) -> PAPostProcessingResult:
    postprocessing_result = object.__new__(PAPostProcessingResult)
    object.__setattr__(postprocessing_result, "original_tokens", original_tokens)
    object.__setattr__(postprocessing_result, "decisions", decisions)
    object.__setattr__(postprocessing_result, "sentence_groups", sentence_groups)
    object.__setattr__(postprocessing_result, "default_threshold", DEFAULT_THRESHOLD)
    object.__setattr__(postprocessing_result, "punctuation_threshold", PUNCTUATION_THRESHOLD)
    object.__setattr__(postprocessing_result, "punctuation_tokens", (".", "؟", "?", "!", "…"))
    object.__setattr__(postprocessing_result, "paragraph_markers", PARAGRAPH_MARKERS)
    object.__setattr__(postprocessing_result, "paragraph_rule_enabled", True)
    object.__setattr__(postprocessing_result, "force_last_enabled", True)
    return postprocessing_result


if __name__ == "__main__":
    unittest.main()
