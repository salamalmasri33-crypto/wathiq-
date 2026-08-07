# AraSeg AI Service Implementation Milestones

## Development Rule

Only one milestone may be implemented at a time.

The next milestone starts only after the current milestone is:

1. Implemented.
2. Tested.
3. Reviewed.
4. Explicitly approved.

Codex or any developer working on this service must stop after completing
the currently approved milestone.

Do not combine several milestones in one change.

---

## Milestone 0 — Protect the Existing Repository

### Goal

Create a safe workspace for the AraSeg AI service without changing the
existing Wathiq applications.

### Tasks

- Create or use a dedicated Git branch:

```text
feature/araseg-ai-service
```

- Confirm the existing repository structure.
- Confirm that existing applications remain unchanged.
- Keep all new AI work under:

```text
wathiq-araseg-service/
```

- Do not modify:
  - `eArchiveSystem`
  - `eArchive.OcrService`
  - `wathiq-frontend`

### Completion Criteria

- The AraSeg branch is ready.
- Existing Wathiq code is protected.
- No existing application behavior has changed.

---

## Milestone 1 — Freeze and Validate the PA Artifact

### Goal

Create a stable production package for the final validated PA model before
building the API service.

### Tasks

- Create the minimal model structure:

```text
wathiq-araseg-service/
└── models/
    └── pa/
        ├── best_model/
        └── manifest.json
```

- Define a typed model-manifest schema.
- Record the validated PA configuration:
  - Maximum length: 512.
  - Stride: 64.
  - Default threshold: 0.567.
  - End-punctuation threshold: 0.32.
  - Paragraph rule: enabled.
  - Force-last rule: enabled.
  - Blind precision: 0.934.
  - Blind recall: 0.939.
  - Blind F1: 0.934.
  - Submission ID: 861529.
- Add SHA256 calculation utilities.
- Add model-artifact validation.
- Add tokenizer-artifact validation.
- Add a local model-loading smoke test.
- Document where the real PA artifact must be copied.

### Restrictions

- Do not create FastAPI yet.
- Do not train or fine-tune a model.
- Do not change thresholds.
- Do not download a replacement model.
- Do not invent missing model paths or hashes.
- Do not use Blind or Test data.

### Tests

- Valid manifest passes.
- Missing manifest fails clearly.
- Missing model files fail clearly.
- Invalid SHA256 fails clearly.
- Model and tokenizer load locally when the real artifact is supplied.
- No network access is required.

### Completion Criteria

- The production manifest is valid.
- Model and tokenizer artifacts are identifiable.
- SHA256 values are recorded.
- Local loading succeeds.
- All Milestone 1 tests pass.

---

## Milestone 2 — FastAPI Skeleton

### Goal

Create the smallest runnable AI service without adding model inference.

### Tasks

- Create the Python application package.
- Add configuration using environment variables.
- Add structured logging.
- Add a FastAPI application entry point.
- Add application startup and shutdown hooks.
- Add:

```http
GET /health
```

- Add Swagger/OpenAPI support.
- Add `.env.example`.
- Add basic service tests.

### Restrictions

- Do not add real model inference.
- Do not load PyTorch inside an API route.
- Do not implement additional tracks.
- Do not modify existing Wathiq applications.

### Tests

- Application starts successfully.
- `/health` returns `200`.
- Swagger loads successfully.
- Configuration values are read from the environment.
- Invalid configuration produces a clear startup error.

### Completion Criteria

- FastAPI starts.
- Swagger works.
- Health tests pass.
- No model code exists inside presentation routes.

---

## Milestone 3 — Abstraction and Fake Pipeline

### Goal

Prove the abstraction-based architecture before adding the real model.

### Tasks

Create:

```text
AbstractSegmentationPipeline
PipelineRegistry
SentenceSegmentationService
FakeSegmentationPipeline
```

Implement the dependency flow:

```text
API Route
→ SentenceSegmentationService
→ PipelineRegistry
→ AbstractSegmentationPipeline
→ FakeSegmentationPipeline
```

- Add a fake implementation for track `PA`.
- Add unit tests for pipeline replacement.
- Add a controlled unsupported-track error.

### Design Patterns

This milestone applies:

- Strategy Pattern.
- Template Method.
- Registry/Factory.

No additional pattern should be introduced without a real requirement.

### Tests

- The route does not instantiate a concrete pipeline.
- The application service depends on the abstraction.
- The fake PA pipeline is resolved through the registry.
- Unsupported tracks fail clearly.
- A different fake implementation can replace the current one without
  changing the route.

### Completion Criteria

- The abstraction works.
- The route is independent from PyTorch and PA implementation details.
- Unit tests pass.

---

## Milestone 4 — Freeze the API Contract

### Goal

Finalize the communication contract before implementing real inference.

### Tasks

- Implement the schemas defined in:

```text
docs/araseg/05_API_CONTRACT.md
```

- Add:

```http
POST /api/v1/segment
```

- Return a fixed fake response matching the final schema.
- Add the standard error-response schema.
- Add OpenAPI examples.
- Review the contract with the ASP.NET integration developer.
- Provide a fixed test request and response.

### Restrictions

- Do not add the real PA model yet.
- Do not rename contract fields after approval without coordination.
- Do not expose internal pipeline classes in public responses.

### Tests

- Valid request returns the expected fake response.
- Invalid request returns a structured error.
- Empty text is rejected.
- Unsupported track is rejected.
- OpenAPI displays the correct schemas.

### Completion Criteria

- The ASP.NET developer can call the fake endpoint.
- Request and response structures are approved.
- Contract tests pass.

---

## Milestone 5 — Standalone Exact PA Inference

### Goal

Port the exact validated PA inference pipeline as standalone Python code
before connecting it to FastAPI.

### Required Inference Flow

```text
Input text
→ safe line-ending normalization
→ paragraph preservation
→ original-token construction
→ tokenizer alignment
→ overlapping chunks
→ model inference
→ probability aggregation
→ PA post-processing
→ sentence reconstruction
→ output validation
```

### Tasks

- Implement local model loading.
- Implement original-token construction.
- Preserve punctuation.
- Preserve paragraph boundaries.
- Implement:
  - Maximum length: 512.
  - Stride: 64.
- Implement subtoken-to-original-token alignment.
- Average probabilities across overlapping chunks.
- Apply:
  - Default threshold: 0.567.
  - End-punctuation threshold: 0.32.
  - Paragraph boundary rule.
  - Force-last rule.
- Reconstruct complete sentences.
- Produce token and sentence metadata.
- Add regression fixtures.

### Restrictions

- Do not connect this milestone to FastAPI.
- Do not train or fine-tune.
- Do not optimize thresholds.
- Do not alter the production tokenizer.
- Do not replace the model.
- Do not access Blind or Test data.

### Critical Invariants

- No original token may be lost.
- Original token order must remain unchanged.
- Every original token must receive one final boundary decision.
- Overlapping chunks must not create duplicate final tokens.
- No empty sentence may be returned.
- The final token must have boundary label `1`.
- Reconstructed sentences must cover the complete input.

### Tests

- One-sentence Arabic text.
- Multiple sentences.
- Multiple paragraphs.
- Text without final punctuation.
- Arabic question mark.
- Arabic and English digits.
- Mixed Arabic and English text.
- Long text requiring several overlapping chunks.
- Token-preservation test.
- Token-order test.
- Deterministic regression test.

### Completion Criteria

- Standalone inference works.
- All critical invariants pass.
- Regression tests pass.
- Results are reproducible.

---

## Milestone 6 — Real PA Pipeline

### Goal

Place the validated standalone inference behind the common abstraction.

### Tasks

- Create:

```text
PAPipeline
```

- Make `PAPipeline` implement or inherit from:

```text
AbstractSegmentationPipeline
```

- Keep PA-specific thresholds and rules inside the PA implementation.
- Compose the inference components instead of putting all logic in one class.
- Load the model once.
- Return the common segmentation result type.
- Keep the application service unchanged.

### Restrictions

- Do not place all inference logic inside `PAPipeline`.
- Do not modify the public API contract.
- Do not implement additional tracks.
- Do not add automatic track routing.

### Tests

- `PAPipeline` is usable through the abstract type.
- The registry resolves `PA` to `PAPipeline`.
- Pipeline output passes all segmentation invariants.
- The application service does not change when fake PA is replaced by real PA.
- Regression tests continue to pass.

### Completion Criteria

- The real PA pipeline works through the abstraction.
- The model loads once.
- Unit and regression tests pass.

---

## Milestone 7 — Real API Integration

### Goal

Replace the fake runtime pipeline with the real PA production pipeline without
changing the API contract.

### Tasks

- Register `PAPipeline` as the PA strategy.
- Keep the route and application service unchanged.
- Add:

```http
GET /api/v1/models
```

- Include:
  - Model version.
  - Model SHA256.
  - Source-text hash.
  - Token count.
  - Boundary count.
  - Processing time.
- Add full API integration tests.

### Tests

- HTTP request reaches the real PA model.
- Response follows the frozen contract.
- Fake and real implementations use the same schema.
- Model metadata is included.
- Invalid requests still return standard errors.

### Completion Criteria

- Real HTTP inference works.
- API contract remains unchanged.
- Integration tests pass.

---

## Milestone 8 — Security and Failure Handling

### Goal

Protect the internal service and return predictable error responses.

### Tasks

- Add:

```text
X-Internal-Api-Key
```

- Validate the key securely.
- Add configurable maximum input size.
- Add centralized exception handling.
- Add request-correlation IDs.
- Map domain and infrastructure exceptions to safe HTTP responses.
- Prevent stack traces and local paths from appearing in responses.

### Error Mappings

- Invalid input → `400`.
- Invalid API key → `401`.
- Unsupported track → `422`.
- Model not ready → `503`.
- Unexpected inference failure → `500`.

### Tests

- Missing API key is rejected.
- Invalid API key is rejected.
- Valid API key is accepted.
- Empty text is rejected.
- Oversized text is rejected.
- Model-not-ready error is structured.
- Unexpected failure does not expose stack traces.

### Completion Criteria

- Security tests pass.
- Error responses follow the frozen contract.
- Logs contain request IDs but not secrets.

---

## Milestone 9 — Resource Management

### Goal

Load and use the production model safely and efficiently.

### Startup Tasks

- Load the manifest.
- Validate model artifacts.
- Validate SHA256 values.
- Load the tokenizer.
- Load the model.
- Select CPU or CUDA from configuration.
- Set the model to evaluation mode.
- Mark the pipeline as ready.

### Inference Tasks

- Use controlled concurrency.
- Use `torch.no_grad()` or inference mode.
- Prevent uncontrolled simultaneous GPU requests.
- Record inference duration.

### Shutdown Tasks

- Release model references.
- Clear GPU cache when appropriate.
- Log shutdown cleanly.

### Restrictions

- Do not load the model for every request.
- Do not download model files at startup.
- Do not introduce a message broker.

### Tests

- Model loads once.
- Readiness changes correctly.
- CPU mode works.
- CUDA configuration fails clearly when unavailable.
- Concurrent requests respect the configured limit.
- Shutdown completes cleanly.

### Completion Criteria

- Resource lifecycle is stable.
- Model readiness is reflected by `/health`.
- No per-request model loading occurs.

---

## Milestone 10 — Docker and Handoff

### Goal

Package the service so the Wathiq integration developer can run it
consistently.

### Tasks

- Add `Dockerfile`.
- Add `docker-compose.yml`.
- Add `.dockerignore`.
- Add `.env.example`.
- Add a container health check.
- Document CPU operation.
- Document GPU operation when supported.
- Document model-volume mounting.
- Document all endpoints and errors.
- Provide test requests.
- Provide timeout and input-size recommendations.

### Tests

- Docker image builds.
- Container starts.
- Health check passes.
- Local model files load through the configured mount.
- Service does not require internet access.
- ASP.NET client can call the container.

### Completion Criteria

- Docker deployment works.
- Handoff documentation is complete.
- ASP.NET integration developer can run and call the service.

---

## Milestone 11 — End-to-End Wathiq Test

### Goal

Verify the complete OCR-to-sentences workflow with the integration developer.

### Shared Test Flow

```text
Upload Arabic document
→ OCR extraction
→ Normalized OCR text
→ AraSeg AI Service
→ Structured sentences
→ Wathiq storage
→ Frontend display
```

### Tasks

- Select one fixed Arabic test document.
- Complete OCR processing.
- Send `NormalizedOcrText` to AraSeg.
- Use `RawOcrText` only as a fallback.
- Receive the structured response.
- Verify the source-text hash.
- Store the segmentation result in Wathiq.
- Display segmented sentences.
- Confirm existing OCR behavior remains unchanged.

### Validation

- No OCR token is lost.
- Sentence order is correct.
- All source text is covered.
- Model version is stored.
- Model SHA256 is stored.
- Failure of AraSeg does not delete OCR output.
- Wathiq can retry segmentation.

### Completion Criteria

- One document completes the full integration path.
- Existing OCR remains functional.
- AraSeg result is visible inside Wathiq.
- Integration evidence is documented.

---

## Future Work — Not Part of Initial Integration

The following work requires separate approval:

- Adding `NoPnxPAPipeline`.
- Adding `NPPipeline`.
- Adding `NoPnxNPPipeline`.
- Automatic OCR-condition routing.
- Sentence-level Elasticsearch indexing.
- Sentence-level embeddings.
- Semantic-search improvements.
- Summarization based on segmented sentences.

These items must not be implemented during the initial PA integration.