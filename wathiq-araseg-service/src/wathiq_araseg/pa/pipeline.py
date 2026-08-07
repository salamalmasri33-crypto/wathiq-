"""Thin PAPipeline orchestration over committed PA inference and post-processing."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from wathiq_araseg.segmentation import (
    AbstractSegmentationPipeline,
    InvalidSegmentationInputError,
    InvalidSegmentationResultError,
    SegmentationRequest,
    SegmentationToken,
    render_segments_from_token_boundaries,
)

from .exceptions import (
    DecisionCoverageMismatchError,
    InvalidInferenceDependencyError,
    InvalidOriginalTokenSequenceError,
    InvalidPAProbabilityResultError,
    MissingFinalBoundaryError,
    PAInferenceError,
    TokenCountMismatchError,
    TokenIndexMismatchError,
    TokenTextMismatchError,
)
from .models import OriginalTokenSequence, PAProbabilityResult
from .postprocessing import PAPostProcessingResult, postprocess_pa_probabilities


class PAPipeline(AbstractSegmentationPipeline):
    """Compose committed PA inference, post-processing, and source-span rendering."""

    def __init__(self, inference_engine: Any) -> None:
        infer_probabilities = getattr(inference_engine, "infer_probabilities", None)
        if not callable(infer_probabilities):
            raise InvalidInferenceDependencyError(
                "PAPipeline requires an inference engine with a callable infer_probabilities(...) method."
            )

        self._inference_engine = inference_engine

    @property
    def track(self) -> str:
        return "PA"

    @property
    def pipeline_id(self) -> str:
        return "pa-current-micro-ensemble-861752"

    def _validate_request(self, request: SegmentationRequest) -> SegmentationRequest:
        validated_request = super()._validate_request(request)
        if validated_request.tokens is None:
            raise InvalidSegmentationInputError(
                "PAPipeline requires a validated internal token sequence."
            )

        return validated_request

    def _run_pipeline(self, request: SegmentationRequest) -> Iterable[str]:
        request_tokens = request.tokens
        if request_tokens is None:
            raise InvalidSegmentationInputError(
                "PAPipeline requires a validated internal token sequence."
            )

        original_tokens = self._build_original_token_sequence(request_tokens)
        probability_result = self._infer_probabilities(original_tokens)
        self._validate_probability_result(request_tokens, original_tokens, probability_result)

        postprocessing_result = self._postprocess_probabilities(probability_result)
        boundary_token_indices = self._derive_boundary_token_indices(
            request_tokens,
            original_tokens,
            postprocessing_result,
        )

        return render_segments_from_token_boundaries(
            normalized_text=request.text,
            tokens=request_tokens,
            boundary_token_indices=boundary_token_indices,
        )

    def _build_original_token_sequence(
        self,
        request_tokens: tuple[SegmentationToken, ...],
    ) -> OriginalTokenSequence:
        try:
            return OriginalTokenSequence(tuple(token.text for token in request_tokens))
        except InvalidOriginalTokenSequenceError as exc:
            raise InvalidSegmentationResultError(
                "PAPipeline could not build a valid original-token sequence from the request tokens."
            ) from exc

    def _infer_probabilities(
        self,
        original_tokens: OriginalTokenSequence,
    ) -> PAProbabilityResult:
        try:
            probability_result = self._inference_engine.infer_probabilities(original_tokens)
        except PAInferenceError as exc:
            raise InvalidSegmentationResultError(
                "PAPipeline inference failed to produce a valid PA probability result."
            ) from exc

        if not isinstance(probability_result, PAProbabilityResult):
            raise InvalidSegmentationResultError(
                "PAPipeline inference must return a PAProbabilityResult."
            )

        return probability_result

    def _validate_probability_result(
        self,
        request_tokens: tuple[SegmentationToken, ...],
        original_tokens: OriginalTokenSequence,
        probability_result: PAProbabilityResult,
    ) -> None:
        expected_tokens = tuple(token.text for token in request_tokens)
        if original_tokens.tokens != expected_tokens:
            raise InvalidSegmentationResultError(
                "PAPipeline original-token construction must preserve exact request token text."
            )

        try:
            if probability_result.original_tokens.tokens != expected_tokens:
                raise TokenTextMismatchError(
                    "PA probability results must preserve exact request token text."
                )

            token_probabilities = probability_result.token_probabilities
            if len(token_probabilities) != len(request_tokens):
                raise TokenCountMismatchError(
                    "PA probability results must preserve the validated request token count."
                )

            for expected_index, (token_span, token_probability) in enumerate(
                zip(request_tokens, token_probabilities, strict=True)
            ):
                if token_probability.token_index != expected_index:
                    raise TokenIndexMismatchError(
                        "PA probability results must preserve sequential token indexes."
                    )
                if token_probability.token != token_span.text:
                    raise TokenTextMismatchError(
                        "PA probability results must preserve exact request token text."
                    )
        except (
            InvalidPAProbabilityResultError,
            TokenCountMismatchError,
            TokenIndexMismatchError,
            TokenTextMismatchError,
        ) as exc:
            raise InvalidSegmentationResultError(
                "PAPipeline inference output did not preserve the validated request tokens exactly."
            ) from exc

    def _postprocess_probabilities(
        self,
        probability_result: PAProbabilityResult,
    ) -> PAPostProcessingResult:
        try:
            postprocessing_result = postprocess_pa_probabilities(probability_result)
        except PAInferenceError as exc:
            raise InvalidSegmentationResultError(
                "PAPipeline post-processing failed to produce valid final boundary decisions."
            ) from exc

        if not isinstance(postprocessing_result, PAPostProcessingResult):
            raise InvalidSegmentationResultError(
                "PAPipeline post-processing must return a PAPostProcessingResult."
            )

        return postprocessing_result

    def _derive_boundary_token_indices(
        self,
        request_tokens: tuple[SegmentationToken, ...],
        original_tokens: OriginalTokenSequence,
        postprocessing_result: PAPostProcessingResult,
    ) -> tuple[int, ...]:
        try:
            if postprocessing_result.original_tokens != original_tokens.tokens:
                raise TokenTextMismatchError(
                    "PA post-processing results must preserve exact request token text."
                )

            decisions = postprocessing_result.decisions
            if len(decisions) != len(request_tokens):
                raise DecisionCoverageMismatchError(
                    "PA post-processing decisions must cover every request token exactly once."
                )

            boundary_token_indices: list[int] = []
            for expected_index, (token_span, decision) in enumerate(
                zip(request_tokens, decisions, strict=True)
            ):
                if decision.token_index != expected_index:
                    raise TokenIndexMismatchError(
                        "PA post-processing decisions must preserve sequential token indexes."
                    )
                if decision.token != token_span.text:
                    raise TokenTextMismatchError(
                        "PA post-processing decisions must preserve exact request token text."
                    )
                if decision.is_boundary:
                    boundary_token_indices.append(decision.token_index)

            if not boundary_token_indices or boundary_token_indices[-1] != len(request_tokens) - 1:
                raise MissingFinalBoundaryError(
                    "PA post-processing must terminate on the final request token."
                )
        except (
            DecisionCoverageMismatchError,
            InvalidPAProbabilityResultError,
            MissingFinalBoundaryError,
            TokenCountMismatchError,
            TokenIndexMismatchError,
            TokenTextMismatchError,
        ) as exc:
            raise InvalidSegmentationResultError(
                "PAPipeline post-processing output did not preserve exact token coverage and boundaries."
            ) from exc

        return tuple(boundary_token_indices)
