"""Frozen fake segmentation endpoint for the Milestone 4 public contract."""

from __future__ import annotations

from hashlib import sha256
from time import perf_counter
from typing import Annotated, cast

from fastapi import APIRouter, Body, Depends, Request, status

from wathiq_araseg.api.errors import ApiContractError
from wathiq_araseg.pa.pipeline import PAPipeline
from wathiq_araseg.api.schemas import (
    ErrorResponseBody,
    RawTextSegmentationRequestBody,
    SegmentationRequestBody,
    SegmentationResponseBody,
    SegmentationSentenceBody,
    TokenizedSegmentationRequestBody,
    TokenizedSegmentationResponseBody,
    TokenizedSegmentationSegmentBody,
)
from wathiq_araseg.segmentation import (
    InvalidSegmentationResultError,
    RawTextSegmentationService,
    SegmentationRequest,
    SegmentationSegment,
    SegmentationToken,
    SentenceSegmentationService,
)

router = APIRouter(prefix="/api/v1", tags=["segmentation"])
internal_router = APIRouter(prefix="/internal/api/v1", tags=["internal-segmentation"])

FAKE_MODEL_VERSION = "fake-pa-contract-v1"
FAKE_MODEL_SHA256 = "fake-contract-marker-not-production"

_REQUEST_EXAMPLE = {
    "documentId": "document-123",
    "text": "النص العربي المستخرج بواسطة OCR",
    "track": "PA",
    "preserveParagraphs": True,
    "returnConfidence": True,
}

_SUCCESS_EXAMPLE = {
    "documentId": "document-123",
    "status": "completed",
    "provider": "AraSeg",
    "track": "PA",
    "modelVersion": FAKE_MODEL_VERSION,
    "modelSha256": FAKE_MODEL_SHA256,
    "sourceTextHash": "f4ab298a1a9ab73e4fc0fa6e1234567890abcdef1234567890abcdef12345678",
    "tokenCount": 1,
    "boundaryCount": 1,
    "processingTimeMs": 0,
    "segmentedText": "النص الكامل",
    "sentences": [
        {
            "index": 0,
            "text": "النص الكامل",
            "startToken": 0,
            "endToken": 0,
            "confidence": 0.0,
            "paragraphIndex": 0,
        }
    ],
}

_INVALID_INPUT_EXAMPLE = {
    "error": {
        "code": "INVALID_INPUT",
        "message": "The request body is invalid.",
        "requestId": "request-identifier",
    }
}

_UNSUPPORTED_TRACK_EXAMPLE = {
    "error": {
        "code": "UNSUPPORTED_TRACK",
        "message": "Only track 'PA' is supported.",
        "requestId": "request-identifier",
    }
}

_INVALID_OPTIONS_EXAMPLE = {
    "error": {
        "code": "INVALID_SEGMENTATION_OPTIONS",
        "message": "preserveParagraphs must be true for track 'PA'.",
        "requestId": "request-identifier",
    }
}

_INTERNAL_REQUEST_EXAMPLE = {
    "documentId": "document-tokenized-123",
    "text": "  هذا .\tنص\n\\n[PAR]!  ",
    "track": "PA",
    "tokens": [
        {"index": 0, "text": "هذا", "startOffset": 2, "endOffset": 5},
        {"index": 1, "text": ".", "startOffset": 6, "endOffset": 7},
        {"index": 2, "text": "نص", "startOffset": 8, "endOffset": 10},
        {"index": 3, "text": "\n", "startOffset": 10, "endOffset": 11},
        {"index": 4, "text": "\\n", "startOffset": 11, "endOffset": 13},
        {"index": 5, "text": "[PAR]", "startOffset": 13, "endOffset": 18},
        {"index": 6, "text": "!", "startOffset": 18, "endOffset": 19},
    ],
}

_INTERNAL_SUCCESS_EXAMPLE = {
    "documentId": "document-tokenized-123",
    "status": "completed",
    "provider": "AraSeg",
    "track": "PA",
    "pipelineId": "pa-current-micro-ensemble-861752",
    "normalizedText": "  هذا .\tنص\n\\n[PAR]!  ",
    "segments": [
        {"index": 0, "text": "  هذا .", "startToken": 0, "endToken": 1},
        {"index": 1, "text": "\tنص\n", "startToken": 2, "endToken": 3},
        {"index": 2, "text": "\\n[PAR]!  ", "startToken": 4, "endToken": 6},
    ],
}

_INTERNAL_RAW_REQUEST_EXAMPLE = {
    "documentId": "document-raw-123",
    "text": "صدر القرار رقم 25. يبدأ التنفيذ غداً.",
    "track": "PA",
}

_INTERNAL_RAW_SUCCESS_EXAMPLE = {
    "documentId": "document-raw-123",
    "status": "completed",
    "provider": "AraSeg",
    "track": "PA",
    "pipelineId": "pa-current-micro-ensemble-861752",
    "normalizedText": "صدر القرار رقم 25. يبدأ التنفيذ غداً.",
    "segments": [
        {
            "index": 0,
            "text": "صدر القرار رقم 25.",
            "startToken": 0,
            "endToken": 4,
        },
        {
            "index": 1,
            "text": " يبدأ التنفيذ غداً.",
            "startToken": 5,
            "endToken": 8,
        },
    ],
}


def get_segmentation_service(request: Request) -> SentenceSegmentationService:
    """Resolve the composed segmentation service from application state."""

    return cast(SentenceSegmentationService, request.app.state.segmentation_service)


def get_internal_pa_pipeline(request: Request) -> PAPipeline:
    """Resolve the startup-retained internal PAPipeline from application state."""

    pipeline = getattr(request.app.state, "internal_pa_pipeline", None)
    if pipeline is None:
        raise ApiContractError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "MODEL_NOT_READY",
            "The internal tokenized PA pipeline is not available.",
        )

    return cast(PAPipeline, pipeline)


def get_internal_pa_raw_text_service(request: Request) -> RawTextSegmentationService:
    """Resolve the startup-retained internal raw-text segmentation service."""

    service = getattr(request.app.state, "internal_pa_raw_text_service", None)
    if service is None:
        raise ApiContractError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "MODEL_NOT_READY",
            "The internal raw-text PA segmentation service is not available.",
        )

    return cast(RawTextSegmentationService, service)


@router.post(
    "/segment",
    response_model=SegmentationResponseBody,
    summary="Segment Arabic OCR text using the frozen fake PA contract.",
    responses={
        status.HTTP_200_OK: {
            "description": "Frozen fake PA segmentation response.",
            "content": {"application/json": {"example": _SUCCESS_EXAMPLE}},
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponseBody,
            "description": "Invalid input or malformed request.",
            "content": {"application/json": {"example": _INVALID_INPUT_EXAMPLE}},
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ErrorResponseBody,
            "description": "Unsupported track or invalid segmentation options.",
            "content": {
                "application/json": {
                    "examples": {
                        "unsupportedTrack": {"value": _UNSUPPORTED_TRACK_EXAMPLE},
                        "invalidSegmentationOptions": {"value": _INVALID_OPTIONS_EXAMPLE},
                    }
                }
            },
        },
    },
)
def segment_text(
    request_body: Annotated[
        SegmentationRequestBody,
        Body(openapi_examples={"default": {"summary": "Fake PA request", "value": _REQUEST_EXAMPLE}}),
    ],
    segmentation_service: Annotated[SentenceSegmentationService, Depends(get_segmentation_service)],
) -> SegmentationResponseBody:
    """Expose the frozen public contract through the fake PA pipeline."""

    normalized_track = request_body.track.strip().upper()
    if normalized_track != "PA":
        raise ApiContractError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "UNSUPPORTED_TRACK",
            "Only track 'PA' is supported.",
        )

    if request_body.preserve_paragraphs is not True:
        raise ApiContractError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "INVALID_SEGMENTATION_OPTIONS",
            "preserveParagraphs must be true for track 'PA'.",
        )

    source_text_hash = sha256(request_body.text.encode("utf-8")).hexdigest()
    started_at = perf_counter()
    domain_result = segmentation_service.segment(_to_domain_request(request_body))
    processing_time_ms = max(0, int((perf_counter() - started_at) * 1000))
    confidence_value = 0.0 if request_body.return_confidence else None

    sentences = tuple(
        SegmentationSentenceBody(
            index=segment.index,
            text=segment.text,
            start_token=0,
            end_token=0,
            confidence=confidence_value,
            paragraph_index=0,
        )
        for segment in domain_result.segments
    )
    segmented_text = "\n".join(sentence.text for sentence in sentences)

    return SegmentationResponseBody(
        document_id=domain_result.document_id,
        status="completed",
        provider="AraSeg",
        track=domain_result.track,
        model_version=FAKE_MODEL_VERSION,
        model_sha256=FAKE_MODEL_SHA256,
        source_text_hash=source_text_hash,
        token_count=1,
        boundary_count=1,
        processing_time_ms=processing_time_ms,
        segmented_text=segmented_text,
        sentences=sentences,
    )


def _to_domain_request(request_body: SegmentationRequestBody) -> SegmentationRequest:
    return SegmentationRequest(
        document_id=request_body.document_id,
        text=request_body.text,
        track=request_body.track,
    )


@internal_router.post(
    "/segment-tokenized",
    response_model=TokenizedSegmentationResponseBody,
    summary="Segment validated tokenized PA input through the real internal pipeline.",
    responses={
        status.HTTP_200_OK: {
            "description": "Exact internal tokenized PA segmentation response.",
            "content": {"application/json": {"example": _INTERNAL_SUCCESS_EXAMPLE}},
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponseBody,
            "description": "Invalid tokenized input or malformed request.",
            "content": {"application/json": {"example": _INVALID_INPUT_EXAMPLE}},
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ErrorResponseBody,
            "description": "Unsupported track.",
            "content": {"application/json": {"example": _UNSUPPORTED_TRACK_EXAMPLE}},
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponseBody,
            "description": "Internal PA inference failed.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponseBody,
            "description": "The real internal PA pipeline is not available.",
        },
    },
)
def segment_tokenized_text(
    request_body: Annotated[
        TokenizedSegmentationRequestBody,
        Body(
            openapi_examples={
                "default": {
                    "summary": "Internal tokenized PA request",
                    "value": _INTERNAL_REQUEST_EXAMPLE,
                }
            }
        ),
    ],
    pipeline: Annotated[PAPipeline, Depends(get_internal_pa_pipeline)],
) -> TokenizedSegmentationResponseBody:
    """Expose the internal tokenized PA contract through the real PAPipeline."""

    normalized_track = request_body.track.strip().upper()
    if normalized_track != "PA":
        raise ApiContractError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "UNSUPPORTED_TRACK",
            "Only track 'PA' is supported.",
        )

    domain_request = _to_tokenized_domain_request(request_body)
    domain_result = pipeline.segment(domain_request)
    request_tokens = domain_request.tokens or ()
    mapped_segments = _map_internal_segments(request_tokens, domain_result.segments)

    return TokenizedSegmentationResponseBody(
        document_id=domain_result.document_id,
        status="completed",
        provider="AraSeg",
        track="PA",
        pipeline_id=domain_result.pipeline_id,
        normalized_text=domain_result.normalized_text,
        segments=mapped_segments,
    )


@internal_router.post(
    "/segment-text",
    response_model=TokenizedSegmentationResponseBody,
    summary="Segment raw-text PA input through the internal raw-text service.",
    responses={
        status.HTTP_200_OK: {
            "description": "Exact internal raw-text PA segmentation response.",
            "content": {"application/json": {"example": _INTERNAL_RAW_SUCCESS_EXAMPLE}},
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponseBody,
            "description": "Invalid raw-text input or malformed request.",
            "content": {"application/json": {"example": _INVALID_INPUT_EXAMPLE}},
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ErrorResponseBody,
            "description": "Unsupported track.",
            "content": {"application/json": {"example": _UNSUPPORTED_TRACK_EXAMPLE}},
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponseBody,
            "description": "Internal PA inference failed.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponseBody,
            "description": "The real internal raw-text PA service is not available.",
        },
    },
)
def segment_raw_text(
    request_body: Annotated[
        RawTextSegmentationRequestBody,
        Body(
            openapi_examples={
                "default": {
                    "summary": "Internal raw-text PA request",
                    "value": _INTERNAL_RAW_REQUEST_EXAMPLE,
                }
            }
        ),
    ],
    raw_text_service: Annotated[
        RawTextSegmentationService,
        Depends(get_internal_pa_raw_text_service),
    ],
) -> TokenizedSegmentationResponseBody:
    """Expose the internal raw-text PA contract through the committed composition path."""

    normalized_track = request_body.track.strip().upper()
    if normalized_track != "PA":
        raise ApiContractError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "UNSUPPORTED_TRACK",
            "Only track 'PA' is supported.",
        )

    domain_request = _to_raw_text_domain_request(request_body)
    raw_text_outcome = raw_text_service.segment_with_tokens(domain_request)
    mapped_segments = _map_internal_segments(
        raw_text_outcome.tokens,
        raw_text_outcome.result.segments,
    )

    return TokenizedSegmentationResponseBody(
        document_id=raw_text_outcome.result.document_id,
        status="completed",
        provider="AraSeg",
        track="PA",
        pipeline_id=raw_text_outcome.result.pipeline_id,
        normalized_text=raw_text_outcome.result.normalized_text,
        segments=mapped_segments,
    )


def _to_raw_text_domain_request(
    request_body: RawTextSegmentationRequestBody,
) -> SegmentationRequest:
    return SegmentationRequest(
        document_id=request_body.document_id,
        text=request_body.text,
        track=request_body.track,
    )


def _to_tokenized_domain_request(
    request_body: TokenizedSegmentationRequestBody,
) -> SegmentationRequest:
    tokens = tuple(
        SegmentationToken(
            index=token.index,
            text=token.text,
            start_offset=token.start_offset,
            end_offset=token.end_offset,
        )
        for token in request_body.tokens
    )

    return SegmentationRequest(
        document_id=request_body.document_id,
        text=request_body.text,
        track=request_body.track,
        tokens=tokens,
    )


def _map_internal_segments(
    tokens: tuple[SegmentationToken, ...],
    segments: tuple[SegmentationSegment, ...],
) -> tuple[TokenizedSegmentationSegmentBody, ...]:
    mapped_segments: list[TokenizedSegmentationSegmentBody] = []
    token_cursor = 0
    source_cursor = 0

    for segment in segments:
        segment_start_offset = source_cursor
        segment_end_offset = source_cursor + len(segment.text)

        while token_cursor < len(tokens) and tokens[token_cursor].end_offset <= segment_start_offset:
            token_cursor += 1

        start_token_index = token_cursor
        end_token_index = token_cursor - 1
        while end_token_index + 1 < len(tokens):
            candidate_token = tokens[end_token_index + 1]
            if candidate_token.start_offset >= segment_end_offset:
                break
            end_token_index += 1

        if start_token_index >= len(tokens) or end_token_index < start_token_index:
            raise InvalidSegmentationResultError(
                "Internal tokenized segmentation could not map exact token coverage for the returned segments."
            )

        mapped_segments.append(
            TokenizedSegmentationSegmentBody(
                index=segment.index,
                text=segment.text,
                start_token=start_token_index,
                end_token=end_token_index,
            )
        )
        token_cursor = end_token_index + 1
        source_cursor = segment_end_offset

    return tuple(mapped_segments)
