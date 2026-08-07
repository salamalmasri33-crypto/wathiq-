"""Deterministic raw-text token-span providers for internal segmentation contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
import unicodedata

from .exceptions import InvalidSegmentationInputError
from .models import SegmentationToken

_LITERAL_PARAGRAPH_MARKER = "[PAR]"
_LITERAL_BACKSLASH_N = "\\n"


class RawTextTokenSpanProvider(ABC):
    """Build exact token spans directly from an authoritative source string."""

    @abstractmethod
    def provide(self, source_text: str) -> tuple[SegmentationToken, ...]:
        """Return an immutable ordered token collection for the supplied source text."""


class LosslessUnicodeTokenSpanProvider(RawTextTokenSpanProvider):
    """Single-pass lossless scanner for natural OCR text under the Wathiq contract."""

    def provide(self, source_text: str) -> tuple[SegmentationToken, ...]:
        if not isinstance(source_text, str):
            raise InvalidSegmentationInputError(
                "Raw-text token span providers require an authoritative string source."
            )

        tokens: list[SegmentationToken] = []
        source_length = len(source_text)
        cursor = 0

        while cursor < source_length:
            if source_text.startswith(_LITERAL_PARAGRAPH_MARKER, cursor):
                tokens.append(
                    _build_token(
                        index=len(tokens),
                        source_text=source_text,
                        start_offset=cursor,
                        end_offset=cursor + len(_LITERAL_PARAGRAPH_MARKER),
                    )
                )
                cursor += len(_LITERAL_PARAGRAPH_MARKER)
                continue

            if source_text.startswith(_LITERAL_BACKSLASH_N, cursor):
                tokens.append(
                    _build_token(
                        index=len(tokens),
                        source_text=source_text,
                        start_offset=cursor,
                        end_offset=cursor + len(_LITERAL_BACKSLASH_N),
                    )
                )
                cursor += len(_LITERAL_BACKSLASH_N)
                continue

            current_character = source_text[cursor]

            if current_character == "\n":
                tokens.append(
                    _build_token(
                        index=len(tokens),
                        source_text=source_text,
                        start_offset=cursor,
                        end_offset=cursor + 1,
                    )
                )
                cursor += 1
                continue

            if current_character == "\r":
                raise InvalidSegmentationInputError(
                    "Raw-text token span providers require LF-only line endings and reject CR or CRLF input."
                )

            if current_character.isspace():
                cursor += 1
                continue

            if _is_unicode_punctuation(current_character):
                tokens.append(
                    _build_token(
                        index=len(tokens),
                        source_text=source_text,
                        start_offset=cursor,
                        end_offset=cursor + 1,
                    )
                )
                cursor += 1
                continue

            token_start_offset = cursor
            cursor += 1
            while cursor < source_length:
                if source_text.startswith(_LITERAL_PARAGRAPH_MARKER, cursor):
                    break
                if source_text.startswith(_LITERAL_BACKSLASH_N, cursor):
                    break

                current_character = source_text[cursor]
                if current_character in ("\n", "\r"):
                    break
                if current_character.isspace():
                    break
                if _is_unicode_punctuation(current_character):
                    break

                cursor += 1

            tokens.append(
                _build_token(
                    index=len(tokens),
                    source_text=source_text,
                    start_offset=token_start_offset,
                    end_offset=cursor,
                )
            )

        return tuple(tokens)


def _build_token(
    *,
    index: int,
    source_text: str,
    start_offset: int,
    end_offset: int,
) -> SegmentationToken:
    return SegmentationToken(
        index=index,
        text=source_text[start_offset:end_offset],
        start_offset=start_offset,
        end_offset=end_offset,
    )


def _is_unicode_punctuation(character: str) -> bool:
    return unicodedata.category(character).startswith("P")
