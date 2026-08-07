# AraSeg AI Service API Contract

## Versioning

Base path:

`/api/v1`

The API contract must remain stable while the PA implementation changes
from a fake pipeline to the real production model.

## Authentication

Internal requests must send:

`X-Internal-Api-Key: <configured-secret>`

The secret must come from environment configuration and must not be committed
to Git.

---

## Health Endpoint

### Request

`GET /health`

### Success Response

```json
{
  "status": "healthy",
  "service": "wathiq-araseg-service",
  "version": "1.0.0",
  "modelReady": true,
  "device": "cpu"
}
```

### Fields

- `status`: Current service status.
- `service`: Service identifier.
- `version`: Current API version.
- `modelReady`: Indicates whether the production model is loaded.
- `device`: The inference device, such as `cpu` or `cuda`.

---

## Models Endpoint

### Request

`GET /api/v1/models`

### Required Header

`X-Internal-Api-Key: <configured-secret>`

### Success Response

```json
{
  "models": [
    {
      "provider": "AraSeg",
      "track": "PA",
      "modelVersion": "pa-final-20260723",
      "ready": true,
      "maxLength": 512,
      "stride": 64
    }
  ]
}
```

Phase 1 exposes only the final PA production pipeline.

---

## Segmentation Endpoint

### Request

`POST /api/v1/segment`

### Required Headers

```text
Content-Type: application/json
X-Internal-Api-Key: <configured-secret>
```

### Request Body

```json
{
  "documentId": "document-123",
  "text": "النص العربي المستخرج بواسطة OCR",
  "track": "PA",
  "preserveParagraphs": true,
  "returnConfidence": true
}
```

### Request Rules

- `documentId` is required.
- `documentId` must not be empty.
- `text` is required.
- `text` must not be empty or whitespace.
- The Wathiq backend should send `NormalizedOcrText`.
- `RawOcrText` may be used only as a fallback.
- Phase 1 supports only `track = "PA"`.
- `preserveParagraphs` must be `true` for the PA pipeline.
- Input text must not exceed the configured maximum size.
- Search content after punctuation or stop-word removal must not be used.

---

## Segmentation Success Response

Status:

`200 OK`

```json
{
  "documentId": "document-123",
  "status": "completed",
  "provider": "AraSeg",
  "track": "PA",
  "modelVersion": "pa-final-20260723",
  "modelSha256": "model-sha256-value",
  "sourceTextHash": "source-text-sha256-value",
  "tokenCount": 20,
  "boundaryCount": 2,
  "processingTimeMs": 180,
  "segmentedText": "الجملة الأولى.\nالجملة الثانية.",
  "sentences": [
    {
      "index": 0,
      "text": "الجملة الأولى.",
      "startToken": 0,
      "endToken": 8,
      "confidence": 0.95,
      "paragraphIndex": 0
    },
    {
      "index": 1,
      "text": "الجملة الثانية.",
      "startToken": 9,
      "endToken": 19,
      "confidence": 0.92,
      "paragraphIndex": 0
    }
  ]
}
```

---

## Response Fields

### `documentId`

The same document identifier received in the request.

### `status`

Successful requests use:

`completed`

### `provider`

Production value:

`AraSeg`

### `track`

The pipeline used for segmentation.

Phase 1 value:

`PA`

### `modelVersion`

The frozen version of the deployed model.

### `modelSha256`

SHA256 identifier of the deployed model artifact.

### `sourceTextHash`

SHA256 hash of the exact OCR text processed by the service.

This allows Wathiq to determine whether the OCR text changed after
segmentation.

### `tokenCount`

Number of original tokens processed by the pipeline.

### `boundaryCount`

Number of final sentence boundaries after applying the PA model rules.

### `processingTimeMs`

Total service-side processing time in milliseconds.

### `segmentedText`

All reconstructed sentences joined using newline characters.

### `sentences`

An ordered list of structured sentence results.

---

## Sentence Object

Each sentence contains:

```json
{
  "index": 0,
  "text": "الجملة الأولى.",
  "startToken": 0,
  "endToken": 8,
  "confidence": 0.95,
  "paragraphIndex": 0
}
```

### Sentence Fields

- `index`: Zero-based sentence index.
- `text`: Reconstructed sentence text.
- `startToken`: Inclusive original-token start index.
- `endToken`: Inclusive original-token end index.
- `confidence`: Optional sentence-level confidence.
- `paragraphIndex`: Zero-based paragraph index when available.

---

## Error Contract

All errors must use the same structure:

```json
{
  "error": {
    "code": "MODEL_NOT_READY",
    "message": "The PA model is not ready.",
    "requestId": "request-correlation-id"
  }
}
```

### Error Fields

- `code`: Stable machine-readable error code.
- `message`: Safe human-readable error message.
- `requestId`: Identifier used to correlate the response with service logs.

The API must not expose:

- Stack traces.
- Local file paths.
- API keys.
- Environment secrets.
- Internal implementation details.

---

## Expected HTTP Errors

### 400 — Invalid Input

Examples:

- Empty `documentId`.
- Empty `text`.
- Text exceeds the configured maximum size.
- Malformed request.

Error code:

`INVALID_INPUT`

### 401 — Unauthorized

Examples:

- Missing internal API key.
- Invalid internal API key.

Error code:

`UNAUTHORIZED`

### 422 — Invalid Request Semantics

Examples:

- Unsupported track.
- `preserveParagraphs` is false for PA.
- Unsupported request-option combination.

Error codes:

- `UNSUPPORTED_TRACK`
- `INVALID_SEGMENTATION_OPTIONS`

### 503 — Model Unavailable

Examples:

- Model files are missing.
- Manifest validation failed.
- Tokenizer failed to load.
- Model is not ready.

Error codes:

- `MODEL_NOT_READY`
- `MODEL_ARTIFACT_MISSING`
- `MODEL_VALIDATION_FAILED`

### 500 — Inference Failure

Used only for unexpected inference errors.

Error code:

`INFERENCE_FAILED`

The original exception must be logged securely but must not be returned to
the API client.

---

## Timeout and Retry Expectations

The ASP.NET client should use a configurable timeout.

Recommended initial timeout:

`120 seconds`

The backend may retry transient failures such as:

- `503 Service Unavailable`.
- Network connection failure.
- Request timeout.

The backend should not automatically retry:

- `400 Bad Request`.
- `401 Unauthorized`.
- `422 Unprocessable Entity`.

---

## Contract Stability Rule

The following fields must not be renamed or removed without coordination
with the ASP.NET integration developer:

- `documentId`
- `text`
- `track`
- `preserveParagraphs`
- `returnConfidence`
- `modelVersion`
- `modelSha256`
- `sourceTextHash`
- `tokenCount`
- `boundaryCount`
- `processingTimeMs`
- `segmentedText`
- `sentences`

The fake pipeline and the real PA pipeline must return the same response
structure.