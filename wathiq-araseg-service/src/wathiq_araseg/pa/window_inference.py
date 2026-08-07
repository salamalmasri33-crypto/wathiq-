"""Standalone PA ensemble window inference and token-probability aggregation."""

from __future__ import annotations

import math
from typing import Any

import torch

from .alignment import TokenizerWindow, build_first_subtoken_alignment
from .exceptions import (
    MissingTokenObservationError,
    NonFiniteModelOutputError,
    ProbabilityShapeMismatchError,
    TokenCountMismatchError,
    TokenizerModelCompatibilityError,
)
from .models import OriginalTokenSequence, PAProbabilityResult, TokenProbability

PA_MAX_LENGTH = 512
PA_STRIDE = 64
PA_BOUNDARY_CLASS_ID = 1
PA_LABEL_COUNT = 2
PA_BASE_WEIGHT = 0.95
PA_MICRO_WEIGHT = 0.05
_WEIGHT_TOLERANCE = 1e-12


class PAEnsembleWindowInferenceEngine:
    """Run standalone PA ensemble window inference over an original-token sequence."""

    def __init__(self, tokenizer: Any, base_model: Any, micro_model: Any) -> None:
        self._tokenizer = tokenizer
        self._base_model = base_model
        self._micro_model = micro_model

        self._validate_weights()
        self._validate_runtime_compatibility()

    def infer_probabilities(
        self,
        original_tokens: OriginalTokenSequence,
    ) -> PAProbabilityResult:
        """Infer base, micro, and blended token probabilities without post-processing."""

        self._base_model.eval()
        self._micro_model.eval()

        alignment = build_first_subtoken_alignment(
            self._tokenizer,
            original_tokens,
            max_length=PA_MAX_LENGTH,
            stride=PA_STRIDE,
        )

        base_observations = [[] for _ in range(original_tokens.token_count)]
        micro_observations = [[] for _ in range(original_tokens.token_count)]

        for window in alignment.windows:
            base_window_probabilities = self._run_window_model(
                self._base_model,
                window,
            )
            micro_window_probabilities = self._run_window_model(
                self._micro_model,
                window,
            )

            for token_index, encoded_position in zip(
                window.original_token_indexes,
                window.encoded_positions,
                strict=True,
            ):
                try:
                    base_observations[token_index].append(
                        base_window_probabilities[encoded_position]
                    )
                    micro_observations[token_index].append(
                        micro_window_probabilities[encoded_position]
                    )
                except IndexError as exc:
                    raise ProbabilityShapeMismatchError(
                        "Window probabilities did not align to tokenizer positions."
                    ) from exc

        token_probabilities = self._build_token_probabilities(
            original_tokens,
            base_observations,
            micro_observations,
        )

        return PAProbabilityResult(
            original_tokens=original_tokens,
            token_probabilities=token_probabilities,
            window_count=alignment.window_count,
            max_length=alignment.max_length,
            stride=alignment.stride,
            base_weight=PA_BASE_WEIGHT,
            micro_weight=PA_MICRO_WEIGHT,
        )

    def _validate_weights(self) -> None:
        if not math.isclose(PA_BASE_WEIGHT, 0.95, rel_tol=0.0, abs_tol=_WEIGHT_TOLERANCE):
            raise TokenizerModelCompatibilityError(
                "Frozen PA ensemble configuration requires a base weight of 0.95."
            )
        if not math.isclose(PA_MICRO_WEIGHT, 0.05, rel_tol=0.0, abs_tol=_WEIGHT_TOLERANCE):
            raise TokenizerModelCompatibilityError(
                "Frozen PA ensemble configuration requires a micro weight of 0.05."
            )
        if not math.isclose(
            PA_BASE_WEIGHT + PA_MICRO_WEIGHT,
            1.0,
            rel_tol=0.0,
            abs_tol=_WEIGHT_TOLERANCE,
        ):
            raise TokenizerModelCompatibilityError(
                "Frozen PA ensemble weights must sum to 1.0."
            )

    def _validate_runtime_compatibility(self) -> None:
        try:
            tokenizer_vocabulary_size = int(len(self._tokenizer))
        except (AttributeError, TypeError, ValueError) as exc:
            raise TokenizerModelCompatibilityError(
                "Tokenizer must expose a stable vocabulary size."
            ) from exc

        for model_name, model in (("base", self._base_model), ("micro", self._micro_model)):
            config = getattr(model, "config", None)
            num_labels = getattr(config, "num_labels", None)
            vocabulary_size = getattr(config, "vocab_size", None)

            if num_labels != PA_LABEL_COUNT:
                raise TokenizerModelCompatibilityError(
                    f"{model_name.capitalize()} model must expose exactly 2 labels."
                )

            if not isinstance(vocabulary_size, int) or vocabulary_size != tokenizer_vocabulary_size:
                raise TokenizerModelCompatibilityError(
                    f"{model_name.capitalize()} model vocabulary must match the tokenizer."
                )

            if num_labels <= PA_BOUNDARY_CLASS_ID:
                raise TokenizerModelCompatibilityError(
                    f"{model_name.capitalize()} model must include boundary class ID 1."
                )

    def _run_window_model(
        self,
        model: Any,
        window: TokenizerWindow,
    ) -> tuple[float, ...]:
        moved_inputs = self._move_inputs_to_model_device(model, window.model_inputs)

        try:
            with torch.inference_mode():
                outputs = model(**moved_inputs)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise TokenizerModelCompatibilityError(
                "Loaded model could not run on the aligned tokenizer window."
            ) from exc

        logits = getattr(outputs, "logits", None)
        if logits is None:
            raise ProbabilityShapeMismatchError(
                "Model outputs must include a logits tensor."
            )

        if getattr(logits, "ndim", None) != 3:
            raise ProbabilityShapeMismatchError(
                "Model logits must have rank 3: [batch, sequence, labels]."
            )
        if int(logits.shape[0]) != 1:
            raise ProbabilityShapeMismatchError(
                "PA window inference expects one tokenizer window per model call."
            )
        if int(logits.shape[-1]) != PA_LABEL_COUNT:
            raise ProbabilityShapeMismatchError(
                "Model logits must expose exactly 2 labels."
            )
        if not torch.isfinite(logits).all().item():
            raise NonFiniteModelOutputError("Model logits must be finite.")

        probabilities = torch.softmax(logits, dim=-1)
        if probabilities.shape != logits.shape:
            raise ProbabilityShapeMismatchError(
                "Softmax probabilities must preserve the logits shape."
            )
        if not torch.isfinite(probabilities).all().item():
            raise NonFiniteModelOutputError("Model probabilities must be finite.")

        class_one_probabilities = probabilities[0, :, PA_BOUNDARY_CLASS_ID]
        if getattr(class_one_probabilities, "ndim", None) != 1:
            raise ProbabilityShapeMismatchError(
                "Boundary probabilities must collapse to one value per encoded position."
            )
        if not torch.isfinite(class_one_probabilities).all().item():
            raise NonFiniteModelOutputError("Boundary probabilities must be finite.")
        if ((class_one_probabilities < 0.0) | (class_one_probabilities > 1.0)).any().item():
            raise NonFiniteModelOutputError(
                "Boundary probabilities must remain within [0, 1]."
            )

        return tuple(float(value) for value in class_one_probabilities.tolist())

    def _move_inputs_to_model_device(
        self,
        model: Any,
        model_inputs: dict[str, Any] | Any,
    ) -> dict[str, Any]:
        device = self._get_model_device(model)
        moved_inputs: dict[str, Any] = {}

        for key, value in model_inputs.items():
            try:
                moved_inputs[key] = value.to(device)
            except AttributeError:
                moved_inputs[key] = value
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                raise TokenizerModelCompatibilityError(
                    "Aligned tokenizer inputs could not be moved to the model device."
                ) from exc

        return moved_inputs

    def _get_model_device(self, model: Any) -> torch.device | str:
        parameters = getattr(model, "parameters", None)
        if callable(parameters):
            try:
                return next(parameters()).device
            except StopIteration:
                return getattr(model, "device", "cpu")
            except (AttributeError, TypeError, ValueError):
                return getattr(model, "device", "cpu")

        return getattr(model, "device", "cpu")

    def _build_token_probabilities(
        self,
        original_tokens: OriginalTokenSequence,
        base_observations: list[list[float]],
        micro_observations: list[list[float]],
    ) -> tuple[TokenProbability, ...]:
        if len(base_observations) != original_tokens.token_count or len(micro_observations) != (
            original_tokens.token_count
        ):
            raise TokenCountMismatchError(
                "Probability aggregation must preserve the original token count."
            )

        token_probabilities: list[TokenProbability] = []
        for token_index, token in enumerate(original_tokens.tokens):
            if not base_observations[token_index]:
                raise MissingTokenObservationError(
                    "Every original token must receive at least one base-model observation."
                )
            if not micro_observations[token_index]:
                raise MissingTokenObservationError(
                    "Every original token must receive at least one micro-model observation."
                )

            base_probability = _arithmetic_mean(base_observations[token_index])
            micro_probability = _arithmetic_mean(micro_observations[token_index])
            blended_probability = (
                (PA_BASE_WEIGHT * base_probability)
                + (PA_MICRO_WEIGHT * micro_probability)
            )

            if not math.isfinite(blended_probability) or not 0.0 <= blended_probability <= 1.0:
                raise NonFiniteModelOutputError(
                    "Blended token probabilities must remain finite and within [0, 1]."
                )

            token_probabilities.append(
                TokenProbability(
                    token_index=token_index,
                    token=token,
                    base_probability=base_probability,
                    micro_probability=micro_probability,
                    blended_probability=blended_probability,
                    base_observation_count=len(base_observations[token_index]),
                    micro_observation_count=len(micro_observations[token_index]),
                )
            )

        return tuple(token_probabilities)


def _arithmetic_mean(values: list[float]) -> float:
    probability = float(sum(values) / len(values))
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise NonFiniteModelOutputError(
            "Aggregated token probabilities must remain finite and within [0, 1]."
        )
    return probability
