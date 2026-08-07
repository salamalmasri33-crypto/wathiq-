# Wathiq Classifier Service

Multi-tenant FastAPI classification service. Each institution has an isolated
taxonomy, examples, persisted embeddings, and in-memory classifier index. The
classification pipeline remains V10 Broad + V18 Specific Weighted RRF K=20.

Authentication, authorization, role checks, and selection of the trusted
`institution_id` belong to the Wathiq backend. This service does not process JWTs.
SQLite is currently used for classifier configuration during development. The
"index" in this project is the in-memory classifier index, not Elasticsearch.

## Run

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Swagger is available at `http://127.0.0.1:8001/docs`.

## Institution API

Import definitions and examples, then classify:

```text
POST /institutions/{institution_id}/config/import-definitions
POST /institutions/{institution_id}/config/import-examples
POST /institutions/{institution_id}/classify
POST /institutions/{institution_id}/classify/debug
```

Classification request:

```json
{"id":"document_123","text":"قرار إداري بتشكيل لجنة لمراجعة ملفات العقود"}
```

Classification response:

```json
{"id":"document_123","broad_genre":"AdministrativeAndOrganizational","specific_genre":"AdministrativeDecision"}
```

The document `id` is returned unchanged and is never embedded. The debug route is
for development only. Legacy routes without an institution remain deprecated
aliases for `DEFAULT_INSTITUTION_ID` and must not be used for new integrations.

## Migration

On first startup with the legacy schema, the service creates
`wathiq_classifier.db.pre_multitenant.bak`, migrates all existing rows and
embeddings to `DEFAULT_INSTITUTION_ID` (default: `default-institution`), and uses
composite institution-scoped keys. Repeated startups do not repeat the migration.

Small two-institution fixtures are in `data/multi_tenant_test`.

## Configuration CRUD workflow

Broad categories, specific types, and examples can be listed, patched, and
deleted under `/institutions/{institution_id}/config`. PATCH requests contain
only changed fields. Taxonomy and example collections can be previewed and
replaced with `PUT ...?dry_run=true` and `PUT ...?confirm=true`.

Deletion workflow:

1. Call the entity's `deletion-impact` endpoint.
2. When `requires_confirmation` is true, show the returned message.
3. Cancel sends no delete request.
4. Confirm sends `DELETE` with `cascade=true` (and `allow_empty_broad=true` when explicitly allowing an empty broad category).
5. Every effective change returns `index_ready=false` and `requires_rebuild=true`.
6. Rebuild once after the editing session with `POST .../config/rebuild-index`.

Cascade deletion and full replacements run in SQLite transactions. Failures are
rolled back before the loaded institution index is invalidated. Every repository
query includes `institution_id`, including dependency counts and embedding cleanup.
