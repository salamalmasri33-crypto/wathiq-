# Wathiq Repository Instructions

## Project Context

Wathiq is an Arabic intelligent document archiving system.

Existing applications:

- `eArchiveSystem`: ASP.NET Core backend.
- `eArchive.OcrService`: OCR microservice.
- `wathiq-frontend`: React frontend.
- `wathiq-araseg-service`: planned Python AI microservice for Arabic sentence segmentation.

The current assignment is limited to the AraSeg AI service.

## Current Owner Scope

The current developer is responsible only for:

- Freezing and validating the final AraSeg production model.
- Building the Python AraSeg AI microservice.
- Implementing sentence-segmentation abstractions.
- Porting the exact validated inference pipeline.
- FastAPI endpoints.
- Unit, regression, and integration tests for the AI service.
- Docker and service documentation.
- Providing a stable API contract to the ASP.NET developer.

Do not implement MongoDB storage, Elasticsearch indexing, React UI,
OCR callback integration, or ASP.NET background jobs unless explicitly requested.

## Non-Destructive Rule

Do not delete, rewrite, rename, or restructure existing applications.

Do not modify:

- `eArchiveSystem`
- `eArchive.OcrService`
- `wathiq-frontend`

unless the task explicitly requests a specific integration change.

New AraSeg work must be isolated under:

`wathiq-araseg-service/`

## Architecture Rules

Follow the existing repository architecture and coding quality.

Apply:

- SOLID principles.
- Clean Code.
- Dependency inversion.
- Small, testable components.
- Explicit configuration.
- Type hints.
- Centralized exception handling.
- Structured logging.

Use design patterns only when they solve a real problem.

Approved patterns for the AraSeg service:

- Strategy Pattern for track-specific pipelines.
- Template Method through an abstract segmentation pipeline.
- Registry/Factory for pipeline resolution.

Do not add unnecessary layers, CQRS, event sourcing, message brokers,
or complex dependency-injection frameworks.

## Abstraction Requirement

FastAPI routes must never call a PyTorch model directly.

The required dependency flow is:

API Route
→ SentenceSegmentationService
→ PipelineRegistry
→ AbstractSegmentationPipeline
→ PAPipeline
→ inference components
→ local model files

The initial concrete implementation is `PAPipeline`.

## Production Model Rule

Integration is inference-only.

Do not:

- train or fine-tune a model;
- optimize thresholds;
- access Blind/Test data;
- download a different model;
- replace the validated production pipeline;
- invent missing model configuration.

The initial production model is the final validated PA pipeline.

Read these documents before making changes:

1. `docs/araseg/01_SHARED_TASK_CONTEXT.md`
2. `docs/araseg/02_FINAL_VALIDATED_PIPELINES.md`
3. `docs/araseg/03_PA_PRODUCTION_SPEC.md`
4. `docs/araseg/04_AI_SERVICE_ARCHITECTURE.md`
5. `docs/araseg/05_API_CONTRACT.md`
6. `docs/araseg/06_IMPLEMENTATION_MILESTONES.md`
7. `docs/araseg/07_REJECTED_EXPERIMENTS.md`

## Incremental Development Rule

Implement only one approved milestone at a time.

For every milestone:

1. Inspect the relevant existing files.
2. Explain the intended change.
3. Modify only the required files.
4. Run the relevant tests.
5. Report created and modified files.
6. Report test results.
7. Stop before starting the next milestone.

Do not implement multiple milestones in one task.

## Testing Rule

No milestone is complete until its tests pass.

Do not weaken, delete, or bypass tests to make a change pass.

Critical invariants for segmentation:

- No source token may be lost.
- Original token order must remain unchanged.
- Every original token must receive exactly one final boundary decision.
- Reconstructed sentences must cover the complete input.
- No empty sentence may be returned.
- The last token must be a boundary for the PA pipeline.
- Model version and SHA256 must be reported.

## Model Storage

Production inference must use local model files.

Do not download models from Hugging Face during application startup or inference.

Do not commit large model binaries to regular Git unless explicitly instructed.
Model paths must be configurable.

## Current Milestone

Do not assume the current milestone.

Read `docs/araseg/06_IMPLEMENTATION_MILESTONES.md` and ask which milestone
is approved when the user has not explicitly identified it.