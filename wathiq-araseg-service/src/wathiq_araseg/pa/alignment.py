"""Fast-tokenizer alignment helpers for standalone PA window inference."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .exceptions import (
    InvalidOriginalTokenSequenceError,
    InvalidWordIdError,
    MissingTokenObservationError,
    UnsupportedTokenizerBehaviorError,
)
from .models import OriginalTokenSequence

_MODEL_INPUT_KEYS = frozenset({"input_ids", "attention_mask", "token_type_ids"})
_PARAGRAPH_MODEL_TOKEN = "[PAR]"
_PA_PARAGRAPH_MARKER_TOKENS = frozenset(("\n", "\\n", _PARAGRAPH_MODEL_TOKEN))


@dataclass(frozen=True, slots=True)
class TokenizerWindow:
    """One aligned tokenizer window with first-subtoken selections."""

    window_index: int
    original_token_indexes: tuple[int, ...]
    encoded_positions: tuple[int, ...]
    model_inputs: Mapping[str, Any]

    def __post_init__(self) -> None:
        if len(self.original_token_indexes) != len(self.encoded_positions):
            raise UnsupportedTokenizerBehaviorError(
                "Aligned tokenizer windows must preserve paired token indexes and positions."
            )


@dataclass(frozen=True, slots=True)
class TokenizerAlignment:
    """Alignment metadata for all tokenizer windows derived from one token sequence."""

    original_tokens: OriginalTokenSequence
    windows: tuple[TokenizerWindow, ...]
    max_length: int
    stride: int

    @property
    def window_count(self) -> int:
        """Return the number of tokenizer windows."""

        return len(self.windows)


def build_pa_model_tokens(
    original_tokens: OriginalTokenSequence | tuple[str, ...],
) -> tuple[str, ...]:
    """Build the exact recovered model-input token sequence for PA inference."""

    source_tokens = (
        original_tokens.tokens
        if isinstance(original_tokens, OriginalTokenSequence)
        else tuple(original_tokens)
    )
    model_tokens = tuple(
        _PARAGRAPH_MODEL_TOKEN if token in _PA_PARAGRAPH_MARKER_TOKENS else token
        for token in source_tokens
    )

    if len(model_tokens) != len(source_tokens):
        raise UnsupportedTokenizerBehaviorError(
            "PA model-input token mapping must preserve token count."
        )

    return model_tokens


def build_first_subtoken_alignment(
    tokenizer: Any,
    original_tokens: OriginalTokenSequence,
    *,
    max_length: int,
    stride: int,
) -> TokenizerAlignment:
    """Tokenize original tokens into overlapping windows and keep first subtokens only."""

    if not isinstance(original_tokens, OriginalTokenSequence):
        raise InvalidOriginalTokenSequenceError(
            "Original tokens must be supplied as an OriginalTokenSequence."
        )

    if getattr(tokenizer, "is_fast", False) is not True:
        raise UnsupportedTokenizerBehaviorError(
            "PA window inference requires a fast tokenizer with word_ids support."
        )

    model_tokens = build_pa_model_tokens(original_tokens)

    try:
        # Overflow windows require padding to materialize a tensor batch safely.
        encoded_batch = tokenizer(
            list(model_tokens),
            is_split_into_words=True,
            truncation=True,
            max_length=max_length,
            stride=stride,
            return_overflowing_tokens=True,
            return_tensors="pt",
            padding=True,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise UnsupportedTokenizerBehaviorError(
            "Tokenizer could not encode original tokens with the required overflow alignment."
        ) from exc

    window_count = _get_window_count(encoded_batch)
    observed_token_indexes = [False] * original_tokens.token_count
    windows: list[TokenizerWindow] = []

    for window_index in range(window_count):
        word_ids = _get_word_ids(encoded_batch, window_index)
        selected_token_indexes: list[int] = []
        selected_positions: list[int] = []
        seen_word_ids: set[int] = set()
        previous_word_id: int | None = None

        for encoded_position, word_id in enumerate(word_ids):
            if word_id is None:
                continue
            if not isinstance(word_id, int):
                raise InvalidWordIdError("Tokenizer word IDs must be integers or None.")
            if word_id < 0 or word_id >= original_tokens.token_count:
                raise InvalidWordIdError("Tokenizer word IDs must remain within token bounds.")
            if word_id in seen_word_ids:
                continue
            if previous_word_id is not None and word_id < previous_word_id:
                raise UnsupportedTokenizerBehaviorError(
                    "Tokenizer word IDs must preserve original token order within each window."
                )

            previous_word_id = word_id
            seen_word_ids.add(word_id)
            observed_token_indexes[word_id] = True
            selected_token_indexes.append(word_id)
            selected_positions.append(encoded_position)

        windows.append(
            TokenizerWindow(
                window_index=window_index,
                original_token_indexes=tuple(selected_token_indexes),
                encoded_positions=tuple(selected_positions),
                model_inputs=_extract_model_inputs(encoded_batch, window_index),
            )
        )

    if not all(observed_token_indexes):
        raise MissingTokenObservationError(
            "Every original token must receive at least one tokenizer-window observation."
        )

    return TokenizerAlignment(
        original_tokens=original_tokens,
        windows=tuple(windows),
        max_length=max_length,
        stride=stride,
    )


def _get_window_count(encoded_batch: Any) -> int:
    input_ids = getattr(encoded_batch, "get", lambda _key, _default=None: None)("input_ids")
    if input_ids is None:
        try:
            input_ids = encoded_batch["input_ids"]
        except (KeyError, TypeError) as exc:
            raise UnsupportedTokenizerBehaviorError(
                "Tokenizer output must include input_ids for each window."
            ) from exc

    shape = getattr(input_ids, "shape", None)
    if shape is None or len(shape) != 2 or int(shape[0]) < 1:
        raise UnsupportedTokenizerBehaviorError(
            "Tokenizer windows must produce a 2D input_ids tensor batch."
        )

    return int(shape[0])


def _get_word_ids(encoded_batch: Any, window_index: int) -> list[int | None]:
    try:
        word_ids = encoded_batch.word_ids(window_index)
    except AttributeError as exc:
        raise UnsupportedTokenizerBehaviorError(
            "Fast-tokenizer outputs must expose word_ids for each overflow window."
        ) from exc
    except (RuntimeError, TypeError, ValueError) as exc:
        raise UnsupportedTokenizerBehaviorError(
            "Tokenizer could not expose word_ids for an overflow window."
        ) from exc

    if not isinstance(word_ids, list):
        raise UnsupportedTokenizerBehaviorError(
            "Tokenizer word_ids output must be a list aligned to encoded positions."
        )

    return word_ids


def _extract_model_inputs(encoded_batch: Any, window_index: int) -> Mapping[str, Any]:
    model_inputs: dict[str, Any] = {}
    for key in _MODEL_INPUT_KEYS:
        try:
            value = encoded_batch[key]
        except (KeyError, TypeError):
            continue

        try:
            model_inputs[key] = value[window_index : window_index + 1]
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            raise UnsupportedTokenizerBehaviorError(
                "Tokenizer window tensors could not be sliced safely."
            ) from exc

    if "input_ids" not in model_inputs:
        raise UnsupportedTokenizerBehaviorError(
            "Tokenizer window inputs must include input_ids."
        )

    return MappingProxyType(model_inputs)
