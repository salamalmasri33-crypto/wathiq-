"""Minimal API error handling for the frozen Milestone 4 contract."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from wathiq_araseg.api.schemas import ErrorDetailBody, ErrorResponseBody
from wathiq_araseg.segmentation import (
    InvalidSegmentationInputError,
    InvalidSegmentationResultError,
    UnsupportedTrackError,
)


class ApiContractError(Exception):
    """Raised for expected API-contract errors with stable HTTP mappings."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def register_error_handlers(app: FastAPI) -> None:
    """Register the minimal Milestone 4 error handlers."""

    @app.exception_handler(ApiContractError)
    async def handle_api_contract_error(_request, exc: ApiContractError) -> JSONResponse:
        return _build_error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(_request, _exc: RequestValidationError) -> JSONResponse:
        return _build_error_response(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_INPUT",
            "The request body is invalid.",
        )

    @app.exception_handler(InvalidSegmentationInputError)
    async def handle_invalid_segmentation_input(
        _request,
        exc: InvalidSegmentationInputError,
    ) -> JSONResponse:
        return _build_error_response(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_INPUT",
            str(exc),
        )

    @app.exception_handler(InvalidSegmentationResultError)
    async def handle_invalid_segmentation_result(
        _request,
        _exc: InvalidSegmentationResultError,
    ) -> JSONResponse:
        return _build_error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INFERENCE_FAILED",
            "The segmentation pipeline failed to produce a valid result.",
        )

    @app.exception_handler(UnsupportedTrackError)
    async def handle_unsupported_track(_request, exc: UnsupportedTrackError) -> JSONResponse:
        return _build_error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "UNSUPPORTED_TRACK",
            str(exc),
        )


def _build_error_response(status_code: int, code: str, message: str) -> JSONResponse:
    payload = ErrorResponseBody(
        error=ErrorDetailBody(
            code=code,
            message=message,
            request_id=uuid4().hex,
        )
    )

    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(by_alias=True),
    )
