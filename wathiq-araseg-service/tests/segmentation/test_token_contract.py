from __future__ import annotations

from pathlib import Path
import sys
import unittest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.segmentation import (  # noqa: E402
    InvalidBoundaryIndexError,
    InvalidTokenIndexError,
    InvalidTokenSequenceError,
    InvalidTokenSpanError,
    MissingFinalBoundaryIndexError,
    SegmentationRequest,
    SegmentationToken,
    SourceSegmentReconstructionError,
    TokenSourceSpanMismatchError,
    render_segments_from_token_boundaries,
)


class SegmentationTokenModelTests(unittest.TestCase):
    def test_valid_token_variants_are_accepted(self) -> None:
        cases = (
            SegmentationToken(index=0, text="كلمة", start_offset=0, end_offset=4),
            SegmentationToken(index=0, text=".", start_offset=0, end_offset=1),
            SegmentationToken(index=0, text=" ", start_offset=0, end_offset=1),
            SegmentationToken(index=0, text="\n", start_offset=0, end_offset=1),
            SegmentationToken(index=0, text="\\n", start_offset=0, end_offset=2),
            SegmentationToken(index=0, text="[PAR]", start_offset=0, end_offset=5),
        )

        for token in cases:
            with self.subTest(token=token.text):
                self.assertIsInstance(token, SegmentationToken)

    def test_empty_token_text_is_rejected(self) -> None:
        with self.assertRaises(InvalidTokenSequenceError):
            SegmentationToken(index=0, text="", start_offset=0, end_offset=1)

    def test_negative_index_is_rejected(self) -> None:
        with self.assertRaises(InvalidTokenIndexError):
            SegmentationToken(index=-1, text="كلمة", start_offset=0, end_offset=4)

    def test_bool_index_is_rejected(self) -> None:
        with self.assertRaises(InvalidTokenIndexError):
            SegmentationToken(index=True, text="كلمة", start_offset=0, end_offset=4)

    def test_negative_start_offset_is_rejected(self) -> None:
        with self.assertRaises(InvalidTokenSpanError):
            SegmentationToken(index=0, text="كلمة", start_offset=-1, end_offset=4)

    def test_end_equal_to_start_is_rejected(self) -> None:
        with self.assertRaises(InvalidTokenSpanError):
            SegmentationToken(index=0, text="كلمة", start_offset=2, end_offset=2)

    def test_end_below_start_is_rejected(self) -> None:
        with self.assertRaises(InvalidTokenSpanError):
            SegmentationToken(index=0, text="كلمة", start_offset=3, end_offset=2)

    def test_bool_offsets_are_rejected(self) -> None:
        with self.assertRaises(InvalidTokenSpanError):
            SegmentationToken(index=0, text="كلمة", start_offset=False, end_offset=4)
        with self.assertRaises(InvalidTokenSpanError):
            SegmentationToken(index=0, text="كلمة", start_offset=0, end_offset=True)


class TokenizedRequestValidationTests(unittest.TestCase):
    def test_valid_tokenized_request_preserves_exact_tuple_and_offsets(self) -> None:
        source = "مرحبا بالعالم."
        tokens = (
            SegmentationToken(index=0, text="مرحبا", start_offset=0, end_offset=5),
            SegmentationToken(index=1, text="بالعالم", start_offset=6, end_offset=13),
            SegmentationToken(index=2, text=".", start_offset=13, end_offset=14),
        )

        request = SegmentationRequest(
            document_id="doc-1",
            text=source,
            track="PA",
            tokens=tokens,
        )

        self.assertEqual(request.tokens, tokens)

    def test_gaps_leading_and_trailing_source_characters_are_allowed(self) -> None:
        source = "  مرحبا بالعالم.  "
        tokens = (
            SegmentationToken(index=0, text="مرحبا", start_offset=2, end_offset=7),
            SegmentationToken(index=1, text="بالعالم", start_offset=8, end_offset=15),
            SegmentationToken(index=2, text=".", start_offset=15, end_offset=16),
        )

        request = SegmentationRequest(
            document_id="doc-2",
            text=source,
            track="PA",
            tokens=tokens,
        )

        self.assertEqual(request.tokens, tokens)

    def test_repeated_spaces_and_tabs_are_preserved_exactly(self) -> None:
        source = "أ\t\tب  ج"
        tokens = (
            SegmentationToken(index=0, text="أ", start_offset=0, end_offset=1),
            SegmentationToken(index=1, text="ب", start_offset=3, end_offset=4),
            SegmentationToken(index=2, text="ج", start_offset=6, end_offset=7),
        )

        request = SegmentationRequest(
            document_id="doc-3",
            text=source,
            track="PA",
            tokens=tokens,
        )

        self.assertEqual(request.tokens, tokens)

    def test_paragraph_representations_validate_against_exact_source_slices(self) -> None:
        source = "أ\nب\\n[PAR]"
        tokens = (
            SegmentationToken(index=0, text="أ", start_offset=0, end_offset=1),
            SegmentationToken(index=1, text="\n", start_offset=1, end_offset=2),
            SegmentationToken(index=2, text="ب", start_offset=2, end_offset=3),
            SegmentationToken(index=3, text="\\n", start_offset=3, end_offset=5),
            SegmentationToken(index=4, text="[PAR]", start_offset=5, end_offset=10),
        )

        request = SegmentationRequest(
            document_id="doc-4",
            text=source,
            track="PA",
            tokens=tokens,
        )

        self.assertEqual(request.tokens, tokens)

    def test_empty_token_tuple_is_rejected(self) -> None:
        with self.assertRaises(InvalidTokenSequenceError):
            SegmentationRequest(
                document_id="doc-5",
                text="مرحبا",
                track="PA",
                tokens=(),
            )

    def test_duplicate_indices_are_rejected(self) -> None:
        with self.assertRaises(InvalidTokenIndexError):
            SegmentationRequest(
                document_id="doc-6",
                text="مرحبا",
                track="PA",
                tokens=(
                    SegmentationToken(index=0, text="مر", start_offset=0, end_offset=2),
                    SegmentationToken(index=0, text="حبا", start_offset=2, end_offset=5),
                ),
            )

    def test_skipped_indices_are_rejected(self) -> None:
        with self.assertRaises(InvalidTokenIndexError):
            SegmentationRequest(
                document_id="doc-7",
                text="مرحبا",
                track="PA",
                tokens=(
                    SegmentationToken(index=0, text="مر", start_offset=0, end_offset=2),
                    SegmentationToken(index=2, text="حبا", start_offset=2, end_offset=5),
                ),
            )

    def test_reordered_indices_or_descending_spans_are_rejected(self) -> None:
        with self.assertRaises(InvalidTokenSpanError):
            SegmentationRequest(
                document_id="doc-8",
                text="أ ب ج",
                track="PA",
                tokens=(
                    SegmentationToken(index=0, text="ب", start_offset=2, end_offset=3),
                    SegmentationToken(index=1, text="أ", start_offset=0, end_offset=1),
                ),
            )

    def test_overlapping_spans_are_rejected(self) -> None:
        with self.assertRaises(InvalidTokenSpanError):
            SegmentationRequest(
                document_id="doc-9",
                text="مرحبا",
                track="PA",
                tokens=(
                    SegmentationToken(index=0, text="مرح", start_offset=0, end_offset=3),
                    SegmentationToken(index=1, text="حبا", start_offset=2, end_offset=5),
                ),
            )

    def test_end_offset_beyond_source_length_is_rejected(self) -> None:
        with self.assertRaises(InvalidTokenSpanError):
            SegmentationRequest(
                document_id="doc-10",
                text="مرحبا",
                track="PA",
                tokens=(
                    SegmentationToken(index=0, text="مرحبا", start_offset=0, end_offset=6),
                ),
            )

    def test_token_text_source_slice_mismatch_is_rejected(self) -> None:
        with self.assertRaises(TokenSourceSpanMismatchError):
            SegmentationRequest(
                document_id="doc-11",
                text="مرحبا",
                track="PA",
                tokens=(
                    SegmentationToken(index=0, text="مرح", start_offset=0, end_offset=2),
                ),
            )


class ExactSourceRenderingTests(unittest.TestCase):
    def test_final_boundary_renders_full_source_text(self) -> None:
        source = "مرحبا بالعالم."
        tokens = (
            SegmentationToken(index=0, text="مرحبا", start_offset=0, end_offset=5),
            SegmentationToken(index=1, text="بالعالم", start_offset=6, end_offset=13),
            SegmentationToken(index=2, text=".", start_offset=13, end_offset=14),
        )

        segments = render_segments_from_token_boundaries(source, tokens, (2,))

        self.assertEqual(segments, (source,))

    def test_multiple_boundaries_preserve_exact_source_slices(self) -> None:
        source = "مرحبا بالعالم. كيف الحال؟"
        tokens = (
            SegmentationToken(index=0, text="مرحبا", start_offset=0, end_offset=5),
            SegmentationToken(index=1, text="بالعالم", start_offset=6, end_offset=13),
            SegmentationToken(index=2, text=".", start_offset=13, end_offset=14),
            SegmentationToken(index=3, text="كيف", start_offset=15, end_offset=18),
            SegmentationToken(index=4, text="الحال", start_offset=19, end_offset=24),
            SegmentationToken(index=5, text="؟", start_offset=24, end_offset=25),
        )

        segments = render_segments_from_token_boundaries(source, tokens, (2, 5))

        self.assertEqual(segments, ("مرحبا بالعالم.", " كيف الحال؟"))
        self.assertEqual("".join(segments), source)

    def test_whitespace_tabs_newlines_and_literals_are_preserved_exactly(self) -> None:
        source = " \tأ\nب\\n[PAR]  "
        tokens = (
            SegmentationToken(index=0, text="أ", start_offset=2, end_offset=3),
            SegmentationToken(index=1, text="\n", start_offset=3, end_offset=4),
            SegmentationToken(index=2, text="ب", start_offset=4, end_offset=5),
            SegmentationToken(index=3, text="\\n", start_offset=5, end_offset=7),
            SegmentationToken(index=4, text="[PAR]", start_offset=7, end_offset=12),
        )

        segments = render_segments_from_token_boundaries(source, tokens, (1, 4))

        self.assertEqual(segments, (" \tأ\n", "ب\\n[PAR]  "))
        self.assertEqual("".join(segments), source)

    def test_valid_boundaries_never_create_empty_segments(self) -> None:
        source = "أ ب"
        tokens = (
            SegmentationToken(index=0, text="أ", start_offset=0, end_offset=1),
            SegmentationToken(index=1, text="ب", start_offset=2, end_offset=3),
        )

        segments = render_segments_from_token_boundaries(source, tokens, (1,))

        self.assertTrue(all(segment != "" for segment in segments))

    def test_invalid_boundary_sequences_are_rejected(self) -> None:
        source = "أ ب ج"
        tokens = (
            SegmentationToken(index=0, text="أ", start_offset=0, end_offset=1),
            SegmentationToken(index=1, text="ب", start_offset=2, end_offset=3),
            SegmentationToken(index=2, text="ج", start_offset=4, end_offset=5),
        )
        invalid_cases = (
            ((), InvalidBoundaryIndexError),
            ((-1, 2), InvalidBoundaryIndexError),
            ((True, 2), InvalidBoundaryIndexError),
            ((1, 1, 2), InvalidBoundaryIndexError),
            ((2, 1), InvalidBoundaryIndexError),
            ((3,), InvalidBoundaryIndexError),
            ((1,), MissingFinalBoundaryIndexError),
        )

        for boundaries, exception_type in invalid_cases:
            with self.subTest(boundaries=boundaries):
                with self.assertRaises(exception_type):
                    render_segments_from_token_boundaries(source, tokens, boundaries)


if __name__ == "__main__":
    unittest.main()
