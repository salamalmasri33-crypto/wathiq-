from __future__ import annotations

import inspect
from pathlib import Path
import sys
import unittest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.segmentation import (
    AbstractSegmentationPipeline,
    InvalidSegmentationInputError,
    InvalidSegmentationResultError,
    InvalidTokenSequenceError,
    LosslessUnicodeTokenSpanProvider,
    PipelineRegistrationError,
    RawTextSegmentationService,
    RawTextTokenSpanProvider,
    SegmentationRequest,
    SegmentationResult,
    SegmentationSegment,
    SegmentationToken,
)


class _RecordingTokenSpanProvider(RawTextTokenSpanProvider):
    def __init__(
        self,
        tokens: tuple[SegmentationToken, ...],
        *,
        error: Exception | None = None,
    ) -> None:
        self.calls: list[str] = []
        self._tokens = tokens
        self._error = error

    def provide(self, source: str) -> tuple[SegmentationToken, ...]:
        self.calls.append(source)
        if self._error is not None:
            raise self._error
        return self._tokens


class _RecordingPipeline(AbstractSegmentationPipeline):
    track = "PA"
    pipeline_id = "recording-pipeline"

    def __init__(
        self,
        *,
        result: SegmentationResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.calls: list[SegmentationRequest] = []
        self._result = result
        self._error = error

    def segment(self, request: SegmentationRequest) -> SegmentationResult:
        self.calls.append(request)
        if self._error is not None:
            raise self._error
        if self._result is None:
            raise AssertionError("A test result must be provided for the recording pipeline.")
        return self._result

    def _run_pipeline(self, request: SegmentationRequest) -> tuple[str, ...]:
        raise AssertionError("The recording pipeline overrides segment() directly.")


class _LifecycleRecordingPipeline(AbstractSegmentationPipeline):
    track = "PA"
    pipeline_id = "lifecycle-recording-pipeline"

    def __init__(self) -> None:
        self.calls: list[SegmentationRequest] = []

    def _run_pipeline(self, request: SegmentationRequest) -> tuple[str, ...]:
        self.calls.append(request)
        return (request.text,)


class RawTextSegmentationServiceTests(unittest.TestCase):
    def test_constructor_requires_expected_dependencies(self) -> None:
        provider = _RecordingTokenSpanProvider(())
        pipeline = _RecordingPipeline(
            result=SegmentationResult(
                document_id="DOC",
                track="PA",
                pipeline_id="recording-pipeline",
                normalized_text="text",
                segments=(SegmentationSegment(index=0, text="text"),),
            )
        )

        with self.assertRaises(PipelineRegistrationError):
            RawTextSegmentationService(object(), pipeline)

        with self.assertRaises(PipelineRegistrationError):
            RawTextSegmentationService(provider, object())

    def test_segment_passes_exact_source_to_provider_once(self) -> None:
        source = "  نص\tبمسافات  "
        tokens = (SegmentationToken(index=0, text="نص", start_offset=2, end_offset=4),)
        provider = _RecordingTokenSpanProvider(tokens)
        expected_result = SegmentationResult(
            document_id="DOC-1",
            track="PA",
            pipeline_id="recording-pipeline",
            normalized_text=source,
            segments=(SegmentationSegment(index=0, text=source),),
        )
        pipeline = _RecordingPipeline(result=expected_result)
        service = RawTextSegmentationService(provider, pipeline)

        result = service.segment(
            SegmentationRequest(document_id="doc-1", text=source, track="PA")
        )

        self.assertEqual(provider.calls, [source])
        self.assertIs(result, expected_result)

    def test_segment_forwards_exact_provider_tokens_to_pipeline_once(self) -> None:
        source = "صدر القرار"
        tokens = (
            SegmentationToken(index=0, text="صدر", start_offset=0, end_offset=3),
            SegmentationToken(index=1, text="القرار", start_offset=4, end_offset=10),
        )
        provider = _RecordingTokenSpanProvider(tokens)
        expected_result = SegmentationResult(
            document_id="DOC-2",
            track="PA",
            pipeline_id="recording-pipeline",
            normalized_text=source,
            segments=(SegmentationSegment(index=0, text=source),),
        )
        pipeline = _RecordingPipeline(result=expected_result)
        service = RawTextSegmentationService(provider, pipeline)

        request = SegmentationRequest(document_id="doc-2", text=source, track="PA")
        result = service.segment(request)

        self.assertIs(result, expected_result)
        self.assertEqual(len(pipeline.calls), 1)
        forwarded_request = pipeline.calls[0]
        self.assertEqual(forwarded_request.document_id, "doc-2")
        self.assertEqual(forwarded_request.text, source)
        self.assertEqual(forwarded_request.track, "PA")
        self.assertEqual(forwarded_request.tokens, tokens)
        self.assertIsNone(request.tokens)

    def test_segment_preserves_whitespace_lf_literal_markers(self) -> None:
        source = "  قبل\tنص\n\\n[PAR] بعد  "
        tokens = (
            SegmentationToken(index=0, text="قبل", start_offset=2, end_offset=5),
            SegmentationToken(index=1, text="نص", start_offset=6, end_offset=8),
            SegmentationToken(index=2, text="\n", start_offset=8, end_offset=9),
            SegmentationToken(index=3, text="\\n", start_offset=9, end_offset=11),
            SegmentationToken(index=4, text="[PAR]", start_offset=11, end_offset=16),
            SegmentationToken(index=5, text="بعد", start_offset=17, end_offset=20),
        )
        provider = _RecordingTokenSpanProvider(tokens)
        expected_result = SegmentationResult(
            document_id="DOC-3",
            track="PA",
            pipeline_id="recording-pipeline",
            normalized_text=source,
            segments=(SegmentationSegment(index=0, text=source),),
        )
        pipeline = _RecordingPipeline(result=expected_result)
        service = RawTextSegmentationService(provider, pipeline)

        service.segment(SegmentationRequest(document_id="doc-3", text=source, track="PA"))

        forwarded_request = pipeline.calls[0]
        self.assertEqual(forwarded_request.text, source)
        self.assertEqual(tuple(token.text for token in forwarded_request.tokens), ("قبل", "نص", "\n", "\\n", "[PAR]", "بعد"))

    def test_empty_source_propagates_existing_token_sequence_error(self) -> None:
        provider = LosslessUnicodeTokenSpanProvider()
        pipeline = _RecordingPipeline(
            result=SegmentationResult(
                document_id="DOC-4",
                track="PA",
                pipeline_id="recording-pipeline",
                normalized_text="",
                segments=(SegmentationSegment(index=0, text="placeholder"),),
            )
        )
        service = RawTextSegmentationService(provider, pipeline)

        with self.assertRaises(InvalidTokenSequenceError):
            service.segment(SegmentationRequest(document_id="doc-4", text="", track="PA"))

        self.assertEqual(len(pipeline.calls), 0)

    def test_whitespace_only_source_propagates_existing_token_sequence_error(self) -> None:
        provider = LosslessUnicodeTokenSpanProvider()
        pipeline = _RecordingPipeline(
            result=SegmentationResult(
                document_id="DOC-4B",
                track="PA",
                pipeline_id="recording-pipeline",
                normalized_text=" \t  ",
                segments=(SegmentationSegment(index=0, text="placeholder"),),
            )
        )
        service = RawTextSegmentationService(provider, pipeline)

        with self.assertRaises(InvalidTokenSequenceError):
            service.segment(
                SegmentationRequest(document_id="doc-4b", text=" \t  ", track="PA")
            )

        self.assertEqual(len(pipeline.calls), 0)

    def test_provider_errors_propagate_unchanged(self) -> None:
        expected_error = InvalidSegmentationInputError("provider failed")
        provider = _RecordingTokenSpanProvider((), error=expected_error)
        pipeline = _RecordingPipeline(
            result=SegmentationResult(
                document_id="DOC-5",
                track="PA",
                pipeline_id="recording-pipeline",
                normalized_text="نص",
                segments=(SegmentationSegment(index=0, text="نص"),),
            )
        )
        service = RawTextSegmentationService(provider, pipeline)

        with self.assertRaises(InvalidSegmentationInputError) as raised:
            service.segment(SegmentationRequest(document_id="doc-5", text="نص", track="PA"))

        self.assertIs(raised.exception, expected_error)
        self.assertEqual(len(pipeline.calls), 0)

    def test_pipeline_errors_propagate_unchanged(self) -> None:
        tokens = (SegmentationToken(index=0, text="نص", start_offset=0, end_offset=2),)
        provider = _RecordingTokenSpanProvider(tokens)
        expected_error = InvalidSegmentationResultError("pipeline failed")
        pipeline = _RecordingPipeline(error=expected_error)
        service = RawTextSegmentationService(provider, pipeline)

        with self.assertRaises(InvalidSegmentationResultError) as raised:
            service.segment(SegmentationRequest(document_id="doc-6", text="نص", track="PA"))

        self.assertIs(raised.exception, expected_error)

    def test_pretokenized_requests_are_rejected(self) -> None:
        source = "نص"
        tokens = (SegmentationToken(index=0, text="نص", start_offset=0, end_offset=2),)
        provider = _RecordingTokenSpanProvider(tokens)
        pipeline = _RecordingPipeline(
            result=SegmentationResult(
                document_id="DOC-7",
                track="PA",
                pipeline_id="recording-pipeline",
                normalized_text=source,
                segments=(SegmentationSegment(index=0, text=source),),
            )
        )
        service = RawTextSegmentationService(provider, pipeline)

        with self.assertRaises(InvalidSegmentationInputError):
            service.segment(
                SegmentationRequest(
                    document_id="doc-7",
                    text=source,
                    track="PA",
                    tokens=tokens,
                )
            )

        self.assertEqual(provider.calls, [])
        self.assertEqual(pipeline.calls, [])

    def test_repeated_execution_is_deterministic_when_dependencies_are_deterministic(self) -> None:
        source = "مرحباً... كيف حالك؟"
        provider = LosslessUnicodeTokenSpanProvider()
        pipeline = _LifecycleRecordingPipeline()
        service = RawTextSegmentationService(provider, pipeline)
        request = SegmentationRequest(document_id="doc-8", text=source, track="PA")

        first_result = service.segment(request)
        second_result = service.segment(request)

        self.assertEqual(first_result, second_result)
        self.assertEqual(len(pipeline.calls), 2)
        self.assertEqual(tuple(token.text for token in pipeline.calls[0].tokens), tuple(token.text for token in pipeline.calls[1].tokens))

    def test_service_contains_no_duplicate_tokenization_or_registry_logic(self) -> None:
        source = inspect.getsource(RawTextSegmentationService)

        forbidden_fragments = (
            "split(",
            "splitlines(",
            "FakeSegmentationPipeline",
            "PipelineRegistry",
            "unicodedata",
            "[PAR]",
            "\\\\n",
        )

        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, source)

    def test_real_provider_composition_preserves_exact_token_source_slices(self) -> None:
        source = "صدر القرار رقم 25. يبدأ التنفيذ غداً."
        provider = LosslessUnicodeTokenSpanProvider()
        pipeline = _LifecycleRecordingPipeline()
        service = RawTextSegmentationService(provider, pipeline)

        result = service.segment(
            SegmentationRequest(document_id="doc-9", text=source, track="PA")
        )

        self.assertEqual(result.normalized_text, source)
        self.assertEqual(tuple(segment.text for segment in result.segments), (source,))
        self.assertEqual(len(pipeline.calls), 1)

        forwarded_request = pipeline.calls[0]
        expected_tokens = (
            "صدر",
            "القرار",
            "رقم",
            "25",
            ".",
            "يبدأ",
            "التنفيذ",
            "غداً",
            ".",
        )
        self.assertEqual(tuple(token.text for token in forwarded_request.tokens), expected_tokens)

        for token in forwarded_request.tokens:
            self.assertEqual(source[token.start_offset : token.end_offset], token.text)


if __name__ == "__main__":
    unittest.main()
