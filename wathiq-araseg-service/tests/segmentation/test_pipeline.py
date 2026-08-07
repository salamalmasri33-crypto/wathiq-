from __future__ import annotations

from pathlib import Path
import sys
import unittest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.segmentation import (  # noqa: E402
    AbstractSegmentationPipeline,
    FakeSegmentationPipeline,
    InvalidSegmentationInputError,
    InvalidSegmentationResultError,
    SegmentationRequest,
    SegmentationToken,
    TokenizedRequestNormalizationError,
)


class PipelineLifecycleTests(unittest.TestCase):
    def test_valid_input_passes_through_abstract_lifecycle(self) -> None:
        pipeline = _RecordingPipeline()
        request = SegmentationRequest(
            document_id="  doc-123  ",
            text="هذا نص\r\nاختباري",
            track=" pa ",
        )

        result = pipeline.segment(request)

        self.assertEqual(request.document_id, "  doc-123  ")
        self.assertEqual(request.text, "هذا نص\r\nاختباري")
        self.assertEqual(request.track, " pa ")
        self.assertEqual(pipeline.seen_document_ids, ["doc-123"])
        self.assertEqual(pipeline.seen_tracks, ["PA"])
        self.assertEqual(pipeline.seen_texts, ["هذا نص\nاختباري"])
        self.assertEqual(pipeline.seen_tokens, [None])
        self.assertEqual(result.document_id, "doc-123")
        self.assertEqual(result.track, "PA")
        self.assertEqual(result.pipeline_id, "recording-pipeline")
        self.assertEqual(result.normalized_text, "هذا نص\nاختباري")
        self.assertEqual(len(result.segments), 1)
        self.assertEqual(result.segments[0].text, "هذا نص\nاختباري")

    def test_valid_tokenized_input_preserves_tokens_through_abstract_lifecycle(self) -> None:
        pipeline = _RecordingPipeline()
        tokens = (
            SegmentationToken(index=0, text="أ", start_offset=0, end_offset=1),
            SegmentationToken(index=1, text="ب", start_offset=2, end_offset=3),
            SegmentationToken(index=2, text="\n", start_offset=3, end_offset=4),
            SegmentationToken(index=3, text="ج", start_offset=4, end_offset=5),
        )
        request = SegmentationRequest(
            document_id="  doc-token  ",
            text="أ ب\nج",
            track=" pa ",
            tokens=tokens,
        )

        result = pipeline.segment(request)

        self.assertEqual(pipeline.seen_document_ids, ["doc-token"])
        self.assertEqual(pipeline.seen_tracks, ["PA"])
        self.assertEqual(pipeline.seen_texts, ["أ ب\nج"])
        self.assertEqual(pipeline.seen_tokens, [tokens])
        self.assertEqual(result.normalized_text, "أ ب\nج")
        self.assertEqual(tuple(segment.text for segment in result.segments), ("أ ب\nج",))

    def test_tokenized_request_with_crlf_is_rejected_before_offset_shift(self) -> None:
        pipeline = _RecordingPipeline()

        with self.assertRaises(TokenizedRequestNormalizationError):
            pipeline.segment(
                SegmentationRequest(
                    document_id="doc-crlf",
                    text="أ\r\nب",
                    track="PA",
                    tokens=(
                        SegmentationToken(index=0, text="أ", start_offset=0, end_offset=1),
                        SegmentationToken(index=1, text="\r\n", start_offset=1, end_offset=3),
                        SegmentationToken(index=2, text="ب", start_offset=3, end_offset=4),
                    ),
                )
            )

    def test_tokenized_request_with_bare_cr_is_rejected_before_offset_shift(self) -> None:
        pipeline = _RecordingPipeline()

        with self.assertRaises(TokenizedRequestNormalizationError):
            pipeline.segment(
                SegmentationRequest(
                    document_id="doc-cr",
                    text="أ\rب",
                    track="PA",
                    tokens=(
                        SegmentationToken(index=0, text="أ", start_offset=0, end_offset=1),
                        SegmentationToken(index=1, text="\r", start_offset=1, end_offset=2),
                        SegmentationToken(index=2, text="ب", start_offset=2, end_offset=3),
                    ),
                )
            )

    def test_blank_document_identifier_is_rejected(self) -> None:
        pipeline = FakeSegmentationPipeline()

        with self.assertRaises(InvalidSegmentationInputError):
            pipeline.segment(
                SegmentationRequest(
                    document_id="   ",
                    text="هذا نص صالح",
                    track="PA",
                )
            )

    def test_blank_text_is_rejected(self) -> None:
        pipeline = FakeSegmentationPipeline()

        with self.assertRaises(InvalidSegmentationInputError):
            pipeline.segment(
                SegmentationRequest(
                    document_id="doc-123",
                    text=" \t\n ",
                    track="PA",
                )
            )

    def test_blank_track_is_rejected(self) -> None:
        pipeline = FakeSegmentationPipeline()

        with self.assertRaises(InvalidSegmentationInputError):
            pipeline.segment(
                SegmentationRequest(
                    document_id="doc-234",
                    text="valid text",
                    track="   ",
                )
            )

    def test_fake_pipeline_preserves_complete_input(self) -> None:
        pipeline = FakeSegmentationPipeline()
        request = SegmentationRequest(
            document_id="doc-456",
            text="هذا هو النص الكامل",
            track="PA",
        )

        result = pipeline.segment(request)

        self.assertEqual(result.normalized_text, request.text)
        self.assertEqual(tuple(segment.text for segment in result.segments), (request.text,))
        self.assertEqual("".join(segment.text for segment in result.segments), request.text)

    def test_fake_pipeline_is_deterministic(self) -> None:
        pipeline = FakeSegmentationPipeline()
        request = SegmentationRequest(
            document_id="doc-789",
            text="نص ثابت",
            track="PA",
        )

        first = pipeline.segment(request)
        second = pipeline.segment(request)

        self.assertEqual(first, second)

    def test_invalid_concrete_output_is_rejected(self) -> None:
        pipeline = _BrokenPipeline()

        with self.assertRaises(InvalidSegmentationResultError):
            pipeline.segment(
                SegmentationRequest(
                    document_id="doc-321",
                    text="نص صحيح",
                    track="PA",
                )
            )


class _RecordingPipeline(AbstractSegmentationPipeline):
    def __init__(self) -> None:
        self.seen_document_ids: list[str] = []
        self.seen_tracks: list[str] = []
        self.seen_texts: list[str] = []
        self.seen_tokens: list[tuple[SegmentationToken, ...] | None] = []

    @property
    def track(self) -> str:
        return "PA"

    @property
    def pipeline_id(self) -> str:
        return "recording-pipeline"

    def _run_pipeline(self, request: SegmentationRequest) -> tuple[str, ...]:
        self.seen_document_ids.append(request.document_id)
        self.seen_tracks.append(request.track)
        self.seen_texts.append(request.text)
        self.seen_tokens.append(request.tokens)
        return (request.text,)


class _BrokenPipeline(AbstractSegmentationPipeline):
    @property
    def track(self) -> str:
        return "PA"

    @property
    def pipeline_id(self) -> str:
        return "broken-pipeline"

    def _run_pipeline(self, _request: SegmentationRequest) -> tuple[str, ...]:
        return ("not-the-original-text",)


if __name__ == "__main__":
    unittest.main()
