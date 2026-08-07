# AraSeg AI Service Architecture

## Responsibility

The service receives Arabic OCR text and returns structured sentences.

It does not store documents, update MongoDB, index Elasticsearch,
or manage the React interface.

## Dependency Flow

FastAPI Route
→ SentenceSegmentationService
→ PipelineRegistry
→ AbstractSegmentationPipeline
→ PAPipeline
→ inference components
→ local production model

## Patterns

### Strategy

Each supported AraSeg track is a separate pipeline strategy.

### Template Method

The abstract base pipeline owns the common lifecycle:

- validation;
- normalization;
- inference orchestration;
- output validation.

Track-specific classes provide the varying behavior.

### Registry

The registry resolves a track identifier to a pipeline instance.

## Initial Scope

Only `PAPipeline` is implemented.

Future classes may include:

- `NoPnxPAPipeline`
- `NPPipeline`
- `NoPnxNPPipeline`

These classes must not be created until their milestone is approved.