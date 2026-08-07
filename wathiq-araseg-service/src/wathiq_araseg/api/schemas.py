"""Public FastAPI schemas for the frozen AraSeg API contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SegmentationRequestBody(BaseModel):
    """Public request schema for fake PA segmentation."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "documentId": "document-123",
                "text": "النص العربي المستخرج بواسطة OCR",
                "track": "PA",
                "preserveParagraphs": True,
                "returnConfidence": True,
            }
        },
    )

    documentId: str
    text: str
    track: str
    preserveParagraphs: bool
    returnConfidence: bool

    @property
    def document_id(self) -> str:
        return self.documentId

    @property
    def preserve_paragraphs(self) -> bool:
        return self.preserveParagraphs

    @property
    def return_confidence(self) -> bool:
        return self.returnConfidence

    @field_validator("documentId")
    @classmethod
    def validate_document_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("documentId must not be blank.")

        return value

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank.")

        return value

    @field_validator("track")
    @classmethod
    def validate_track(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("track must not be blank.")

        return value


class SegmentationSentenceBody(BaseModel):
    """Public response sentence schema for the frozen fake contract."""

    model_config = ConfigDict(populate_by_name=True)

    index: int
    text: str
    start_token: int = Field(alias="startToken")
    end_token: int = Field(alias="endToken")
    confidence: float | None
    paragraph_index: int = Field(alias="paragraphIndex")


class SegmentationResponseBody(BaseModel):
    """Public success response schema for fake PA segmentation."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "documentId": "document-123",
                "status": "completed",
                "provider": "AraSeg",
                "track": "PA",
                "modelVersion": "fake-pa-contract-v1",
                "modelSha256": "fake-contract-marker-not-production",
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
        },
    )

    document_id: str = Field(alias="documentId")
    status: Literal["completed"]
    provider: Literal["AraSeg"]
    track: str
    model_version: str = Field(alias="modelVersion")
    model_sha256: str = Field(alias="modelSha256")
    source_text_hash: str = Field(alias="sourceTextHash")
    token_count: int = Field(alias="tokenCount")
    boundary_count: int = Field(alias="boundaryCount")
    processing_time_ms: int = Field(alias="processingTimeMs")
    segmented_text: str = Field(alias="segmentedText")
    sentences: tuple[SegmentationSentenceBody, ...]


class TokenizedSegmentationTokenBody(BaseModel):
    """Internal token-span request object for exact PA segmentation."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    index: int = Field(strict=True)
    text: str
    start_offset: int = Field(alias="startOffset", strict=True)
    end_offset: int = Field(alias="endOffset", strict=True)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if value == "":
            raise ValueError("Token text must not be empty.")

        return value


class RawTextSegmentationRequestBody(BaseModel):
    """Internal request schema for raw-text PA segmentation."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "documentId": "document-raw-123",
                "text": "صدر القرار رقم 25. يبدأ التنفيذ غداً.",
                "track": "PA",
            }
        },
    )

    documentId: str
    text: str
    track: str

    @property
    def document_id(self) -> str:
        return self.documentId

    @field_validator("documentId")
    @classmethod
    def validate_document_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("documentId must not be blank.")

        return value

    @field_validator("track")
    @classmethod
    def validate_track(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("track must not be blank.")

        return value


class TokenizedSegmentationRequestBody(BaseModel):
    """Internal request schema for tokenized PA segmentation."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
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
        },
    )

    documentId: str
    text: str
    track: str
    tokens: tuple[TokenizedSegmentationTokenBody, ...]

    @property
    def document_id(self) -> str:
        return self.documentId

    @field_validator("documentId")
    @classmethod
    def validate_document_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("documentId must not be blank.")

        return value

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank.")

        return value

    @field_validator("track")
    @classmethod
    def validate_track(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("track must not be blank.")

        return value

    @field_validator("tokens")
    @classmethod
    def validate_tokens(cls, value: tuple[TokenizedSegmentationTokenBody, ...]) -> tuple[TokenizedSegmentationTokenBody, ...]:
        if not value:
            raise ValueError("tokens must contain at least one token.")

        return value


class TokenizedSegmentationSegmentBody(BaseModel):
    """Internal exact-source segment schema for tokenized PA segmentation."""

    model_config = ConfigDict(populate_by_name=True)

    index: int
    text: str
    start_token: int = Field(alias="startToken")
    end_token: int = Field(alias="endToken")


class TokenizedSegmentationResponseBody(BaseModel):
    """Internal response schema for exact tokenized PA segmentation."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
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
        },
    )

    document_id: str = Field(alias="documentId")
    status: Literal["completed"]
    provider: Literal["AraSeg"]
    track: Literal["PA"]
    pipeline_id: str = Field(alias="pipelineId")
    normalized_text: str = Field(alias="normalizedText")
    segments: tuple[TokenizedSegmentationSegmentBody, ...]


class ErrorDetailBody(BaseModel):
    """Public error-detail schema."""

    model_config = ConfigDict(populate_by_name=True)

    code: str
    message: str
    request_id: str = Field(alias="requestId")


class ErrorResponseBody(BaseModel):
    """Public API error envelope schema."""

    model_config = ConfigDict(populate_by_name=True)

    error: ErrorDetailBody
