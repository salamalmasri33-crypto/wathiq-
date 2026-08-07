from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .database import SQLiteStore
from .embeddings import EmbeddingModels
from .schemas import (
    ClassifyRequest, ClassifyResponse, DebugClassifyResponse, DefinitionsPayload,
    ExamplesPayload, ExamplesUpsert, ImportResponse, RebuildResponse,
    SingleBroadUpsert, SingleSpecificUpsert, BroadPatch, SpecificPatch, ExamplePatch,
    MutationResponse, DeletionImpactResponse, DeleteResponse, ExampleDeleteResponse,
    ReplacementPreviewResponse,
    BroadRecordResponse, SpecificRecordResponse, ExampleRecordResponse,
    BroadListResponse, SpecificListResponse, ExampleListResponse,
)
from .settings import settings
from .tenant_manager import InstitutionClassifierManager


InstitutionId = Annotated[
    str,
    Path(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
        description="Trusted institution identifier supplied by the Wathiq backend.",
        examples=["institution_123"],
    ),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = SQLiteStore(settings.database_path, settings.default_institution_id)
    models = EmbeddingModels(settings)
    manager = InstitutionClassifierManager(store, models, settings)
    app.state.store = store
    app.state.models = models
    app.state.manager = manager
    yield
    store.close()


app = FastAPI(
    title=settings.service_name,
    version="2.0.0",
    description="Multi-tenant Wathiq classifier using the unchanged V10 Broad + V18 Specific K=20 pipeline.",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Health"},
        {"name": "Institution Configuration"},
        {"name": "Institution Taxonomy"},
        {"name": "Institution Examples"},
        {"name": "Institution Deletion Preview"},
        {"name": "Institution Index Management"},
        {"name": "Institution Classification"},
        {"name": "Development Debug"},
        {"name": "Deprecated Default Institution"},
    ],
)


def get_store(request: Request) -> SQLiteStore:
    return request.app.state.store


def get_manager(request: Request) -> InstitutionClassifierManager:
    return request.app.state.manager


async def parse_uploaded_json(file: UploadFile) -> dict:
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Only JSON files are accepted")
    try:
        return json.loads((await file.read()).decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="JSON must be UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health", tags=["Health"])
async def health(request: Request):
    manager = get_manager(request)
    models = request.app.state.models
    return {
        "status": "ok",
        "database": str(settings.database_path),
        "models_loaded": bool(models.status()["e5_loaded"] and models.status()["arabic_loaded"]),
        "configured_institutions": get_store(request).configured_institutions(),
        "loaded_indexes": manager.loaded_indexes,
        "last_error": None,
    }


@app.get("/institutions/{institution_id}/config/status", tags=["Institution Configuration"])
async def institution_status(institution_id: InstitutionId, request: Request):
    store, manager = get_store(request), get_manager(request)
    if not store.institution_exists(institution_id):
        raise HTTPException(404, "Classification configuration was not found for this institution")
    classifier = manager.get(institution_id)
    return {"institution_id": institution_id, "index_ready": classifier.ready,
            "statistics": store.statistics(institution_id), "last_updated": store.last_updated(institution_id),
            "last_error": classifier.last_error}


@app.get("/institutions/{institution_id}/config/taxonomy", tags=["Institution Configuration"])
async def taxonomy(institution_id: InstitutionId, request: Request):
    return get_store(request).taxonomy(institution_id)


@app.get("/institutions/{institution_id}/config/examples",response_model=ExampleListResponse,tags=["Institution Examples"])
async def examples(institution_id: InstitutionId, request: Request, broad_id: str | None = None, specific_id: str | None = None, limit: int = Query(100,ge=1,le=1000), offset: int = Query(0,ge=0)):
    return {"examples": get_store(request).list_examples(institution_id,False,broad_id,specific_id,limit,offset)}


async def do_import_definitions(institution_id: str, payload: DefinitionsPayload, request: Request):
    store, manager = get_store(request), get_manager(request)
    imported = await run_in_threadpool(store.replace_definitions, institution_id, payload)
    manager.invalidate(institution_id)
    await run_in_threadpool(manager.sync_definitions, institution_id)
    return ImportResponse(imported=imported, index_ready=False)


@app.post("/institutions/{institution_id}/config/import-definitions", response_model=ImportResponse, tags=["Institution Configuration"])
async def import_definitions(institution_id: InstitutionId, payload: DefinitionsPayload, request: Request):
    return await do_import_definitions(institution_id, payload, request)


@app.post("/institutions/{institution_id}/config/import-definitions-file", response_model=ImportResponse, tags=["Institution Configuration"])
async def import_definitions_file(institution_id: InstitutionId, request: Request, file: UploadFile = File(...)):
    return await do_import_definitions(institution_id, DefinitionsPayload.model_validate(await parse_uploaded_json(file)), request)


async def do_import_examples(institution_id: str, payload: ExamplesPayload, request: Request):
    store, manager = get_store(request), get_manager(request)
    if not store.institution_exists(institution_id):
        raise HTTPException(404, "Classification configuration was not found for this institution")
    imported = await run_in_threadpool(store.replace_examples, institution_id, payload)
    await run_in_threadpool(manager.sync_examples, institution_id)
    manager.invalidate(institution_id)
    return ImportResponse(imported=imported, index_ready=False, warnings=manager.get(institution_id).warnings)


@app.post("/institutions/{institution_id}/config/import-examples", response_model=ImportResponse, tags=["Institution Configuration"])
async def import_examples(institution_id: InstitutionId, payload: ExamplesPayload, request: Request):
    return await do_import_examples(institution_id, payload, request)


@app.post("/institutions/{institution_id}/config/import-examples-file", response_model=ImportResponse, tags=["Institution Configuration"])
async def import_examples_file(institution_id: InstitutionId, request: Request, file: UploadFile = File(...)):
    return await do_import_examples(institution_id, ExamplesPayload.model_validate(await parse_uploaded_json(file)), request)


@app.post("/institutions/{institution_id}/config/broad", response_model=MutationResponse, tags=["Institution Taxonomy"])
async def upsert_broad(institution_id: InstitutionId, payload: SingleBroadUpsert, request: Request):
    store, manager = get_store(request), get_manager(request)
    await run_in_threadpool(store.upsert_broad, institution_id, payload.broad.model_dump(exclude={"specific_types"}))
    for specific in payload.broad.specific_types:
        await run_in_threadpool(store.upsert_specific, institution_id, payload.broad.broad_category, specific.model_dump())
    manager.invalidate(institution_id)
    await run_in_threadpool(manager.sync_definitions, institution_id)
    manager.invalidate(institution_id)
    return MutationResponse(success=True,message="Broad category saved successfully",entity_id=payload.broad.broad_category)


@app.post("/institutions/{institution_id}/config/specific", response_model=MutationResponse, tags=["Institution Taxonomy"])
async def upsert_specific(institution_id: InstitutionId, payload: SingleSpecificUpsert, request: Request):
    store, manager = get_store(request), get_manager(request)
    await run_in_threadpool(store.upsert_specific, institution_id, payload.broad_category, payload.specific.model_dump())
    manager.invalidate(institution_id)
    await run_in_threadpool(manager.sync_definitions, institution_id)
    manager.invalidate(institution_id)
    return MutationResponse(success=True,message="Specific type saved successfully",entity_id=payload.specific.specific_type)


@app.post("/institutions/{institution_id}/config/examples", response_model=MutationResponse, tags=["Institution Examples"])
async def upsert_examples(institution_id: InstitutionId, payload: ExamplesUpsert, request: Request):
    store, manager = get_store(request), get_manager(request)
    await run_in_threadpool(store.upsert_examples, institution_id, payload.examples)
    await run_in_threadpool(manager.sync_examples,institution_id,[item.id for item in payload.examples])
    manager.invalidate(institution_id)
    return MutationResponse(success=True,message="Examples saved successfully",entity_id=",".join(item.id for item in payload.examples))


@app.get("/institutions/{institution_id}/config/broad",response_model=BroadListResponse,tags=["Institution Taxonomy"], description="Lists broad categories without modifying the index.")
async def list_broad_categories(institution_id: InstitutionId, request: Request):
    return {"broad_categories":get_store(request).list_broad(institution_id,False)}


@app.get("/institutions/{institution_id}/config/broad/{broad_id}",response_model=BroadRecordResponse,tags=["Institution Taxonomy"])
async def get_broad_category(institution_id: InstitutionId,broad_id: str,request: Request):
    result=get_store(request).broad_detail(institution_id,broad_id)
    if not result: raise HTTPException(404,"Broad category was not found")
    return result


@app.patch("/institutions/{institution_id}/config/broad/{broad_id}",response_model=MutationResponse,tags=["Institution Taxonomy"],description="Updates selected fields, refreshes affected definition embeddings, and requires a later rebuild.")
async def update_broad_category(institution_id: InstitutionId,broad_id: str,payload: BroadPatch,request: Request):
    store,manager=get_store(request),get_manager(request)
    if not await run_in_threadpool(store.patch_broad,institution_id,broad_id,payload.model_dump(exclude_unset=True)): raise HTTPException(404,"Broad category was not found")
    manager.invalidate(institution_id); await run_in_threadpool(manager.sync_definitions,institution_id); manager.invalidate(institution_id)
    return MutationResponse(success=True,message="Broad category updated successfully",entity_id=broad_id)


def broad_impact_response(institution_id: str,broad_id: str,dependencies: dict[str,int]) -> DeletionImpactResponse:
    confirmation=bool(dependencies["specific_types"] or dependencies["examples"])
    return DeletionImpactResponse(institution_id=institution_id,entity_type="broad",entity_id=broad_id,can_delete_directly=not confirmation,requires_confirmation=confirmation,dependencies=dependencies,message_ar=(f"يحتوي هذا التصنيف على {dependencies['specific_types']} تصنيفات فرعية و{dependencies['examples']} مثالا. سيؤدي تأكيد الحذف إلى حذف جميع العناصر التابعة." if confirmation else "يمكن حذف التصنيف دون حذف تصنيفات فرعية أو أمثلة."),message_en=(f"This category contains {dependencies['specific_types']} specific types and {dependencies['examples']} examples. Confirming deletion will remove all dependent items." if confirmation else "The category can be deleted without removing specific types or examples."))


@app.get("/institutions/{institution_id}/config/broad/{broad_id}/deletion-impact",response_model=DeletionImpactResponse,tags=["Institution Deletion Preview"])
async def preview_broad_deletion(institution_id: InstitutionId,broad_id: str,request: Request):
    impact=get_store(request).broad_deletion_impact(institution_id,broad_id)
    if impact is None: raise HTTPException(404,"Broad category was not found")
    return broad_impact_response(institution_id,broad_id,impact)


@app.delete("/institutions/{institution_id}/config/broad/{broad_id}",response_model=DeleteResponse,tags=["Institution Taxonomy"],description="Requires cascade=true when dependent specific types or examples exist; successful deletion requires a rebuild.")
async def delete_broad_category(institution_id: InstitutionId,broad_id: str,request: Request,cascade: bool=False):
    store,manager=get_store(request),get_manager(request); impact=store.broad_deletion_impact(institution_id,broad_id)
    if impact is None: raise HTTPException(404,"Broad category was not found")
    if (impact["specific_types"] or impact["examples"]) and not cascade:
        return DeleteResponse(success=False,deleted=False,requires_confirmation=True,dependencies=impact,message_ar="يتطلب حذف هذا التصنيف تأكيدا بسبب وجود عناصر تابعة.",message_en="Deleting this category requires confirmation because it has dependent items.")
    counts=await run_in_threadpool(store.delete_broad,institution_id,broad_id); manager.invalidate(institution_id)
    return DeleteResponse(success=True,deleted=True,deleted_counts=counts,index_ready=False,requires_rebuild=True,message_ar="تم حذف التصنيف وجميع العناصر التابعة له.",message_en="The category and all dependent items were deleted.")


@app.get("/institutions/{institution_id}/config/specific",response_model=SpecificListResponse,tags=["Institution Taxonomy"])
async def list_specific_types(institution_id: InstitutionId,request: Request,broad_id: str|None=None):
    return {"specific_types":get_store(request).list_specific(institution_id,False,broad_id)}


@app.get("/institutions/{institution_id}/config/specific/{specific_id}",response_model=SpecificRecordResponse,tags=["Institution Taxonomy"])
async def get_specific_type(institution_id: InstitutionId,specific_id: str,request: Request):
    result=get_store(request).get_specific(institution_id,specific_id)
    if not result: raise HTTPException(404,"Specific type was not found")
    return result


@app.patch("/institutions/{institution_id}/config/specific/{specific_id}",response_model=MutationResponse,tags=["Institution Taxonomy"])
async def update_specific_type(institution_id: InstitutionId,specific_id: str,payload: SpecificPatch,request: Request):
    store,manager=get_store(request),get_manager(request)
    if not await run_in_threadpool(store.patch_specific,institution_id,specific_id,payload.model_dump(exclude_unset=True)): raise HTTPException(404,"Specific type was not found")
    manager.invalidate(institution_id); await run_in_threadpool(manager.sync_definitions,institution_id); manager.invalidate(institution_id)
    return MutationResponse(success=True,message="Specific type updated successfully",entity_id=specific_id)


@app.get("/institutions/{institution_id}/config/specific/{specific_id}/deletion-impact",response_model=DeletionImpactResponse,tags=["Institution Deletion Preview"])
async def preview_specific_deletion(institution_id: InstitutionId,specific_id: str,request: Request):
    impact=get_store(request).specific_deletion_impact(institution_id,specific_id)
    if impact is None: raise HTTPException(404,"Specific type was not found")
    confirmation=bool(impact["examples"])
    return DeletionImpactResponse(institution_id=institution_id,entity_type="specific",entity_id=specific_id,can_delete_directly=not confirmation,requires_confirmation=confirmation,dependencies=impact,message_ar=(f"يحتوي هذا التصنيف على {impact['examples']} أمثلة. سيؤدي تأكيد الحذف إلى حذفها." if confirmation else "يمكن حذف التصنيف الفرعي مباشرة."),message_en=(f"This specific type contains {impact['examples']} examples. Confirming deletion will remove them." if confirmation else "The specific type can be deleted directly."))


@app.delete("/institutions/{institution_id}/config/specific/{specific_id}",response_model=DeleteResponse,tags=["Institution Taxonomy"])
async def delete_specific_type(institution_id: InstitutionId,specific_id: str,request: Request,cascade: bool=False,allow_empty_broad: bool=False):
    store,manager=get_store(request),get_manager(request); current=store.get_specific(institution_id,specific_id)
    if not current: raise HTTPException(404,"Specific type was not found")
    impact=store.specific_deletion_impact(institution_id,specific_id) or {}
    active=[row for row in store.list_specific(institution_id,True,current["broad_id"]) if row["id"]!=specific_id]
    needs=bool(impact["examples"])
    if needs and not cascade: return DeleteResponse(success=False,deleted=False,requires_confirmation=True,dependencies=impact,message_ar="يتطلب الحذف تأكيدا بسبب وجود أمثلة تابعة.",message_en="Deletion requires confirmation because dependent examples exist.")
    if current["is_active"] and not active and not allow_empty_broad: return DeleteResponse(success=False,deleted=False,requires_confirmation=True,dependencies=impact,message_ar="هذا آخر تصنيف فرعي فعال. استخدم allow_empty_broad=true للتأكيد.",message_en="This is the last active specific type. Use allow_empty_broad=true to confirm.")
    counts=await run_in_threadpool(store.delete_specific,institution_id,specific_id); manager.invalidate(institution_id)
    return DeleteResponse(success=True,deleted=True,deleted_counts=counts,index_ready=False,requires_rebuild=True,message_ar="تم حذف التصنيف الفرعي والعناصر التابعة.",message_en="The specific type and dependent items were deleted.")


@app.get("/institutions/{institution_id}/config/examples/{example_id}",response_model=ExampleRecordResponse,tags=["Institution Examples"])
async def get_example(institution_id: InstitutionId,example_id: str,request: Request):
    result=get_store(request).get_example(institution_id,example_id)
    if not result: raise HTTPException(404,"Example was not found")
    return result


@app.patch("/institutions/{institution_id}/config/examples/{example_id}",response_model=MutationResponse,tags=["Institution Examples"])
async def update_example(institution_id: InstitutionId,example_id: str,payload: ExamplePatch,request: Request):
    store,manager=get_store(request),get_manager(request)
    if not await run_in_threadpool(store.patch_example,institution_id,example_id,payload.model_dump(exclude_unset=True)): raise HTTPException(404,"Example was not found")
    await run_in_threadpool(manager.sync_examples,institution_id,[example_id]); manager.invalidate(institution_id)
    return MutationResponse(success=True,message="Example updated successfully",entity_id=example_id)


@app.delete("/institutions/{institution_id}/config/examples/{example_id}",response_model=ExampleDeleteResponse,tags=["Institution Examples"])
async def delete_example(institution_id: InstitutionId,example_id: str,request: Request):
    store,manager=get_store(request),get_manager(request)
    if not await run_in_threadpool(store.delete_example,institution_id,example_id): raise HTTPException(404,"Example was not found")
    manager.invalidate(institution_id); return ExampleDeleteResponse(success=True,deleted=True,example_id=example_id)


@app.put("/institutions/{institution_id}/config/taxonomy",response_model=ReplacementPreviewResponse,tags=["Institution Taxonomy"],description="Validates and previews replacement with dry_run=true. Destructive replacement requires confirm=true and leaves the index requiring rebuild.")
async def replace_taxonomy(institution_id: InstitutionId,payload: DefinitionsPayload,request: Request,dry_run: bool=False,confirm: bool=False):
    store,manager=get_store(request),get_manager(request); impact=store.taxonomy_replacement_impact(institution_id,payload)
    destructive=any(impact["will_delete"].values())
    response=ReplacementPreviewResponse(will_replace=impact["will_replace"],will_delete=impact["will_delete"],requires_confirmation=destructive,applied=False)
    if dry_run or (destructive and not confirm): return response
    await run_in_threadpool(store.replace_taxonomy,institution_id,payload)
    manager.invalidate(institution_id); await run_in_threadpool(manager.sync_definitions,institution_id); manager.invalidate(institution_id)
    return response.model_copy(update={"applied":True,"index_ready":False,"requires_rebuild":True,"requires_confirmation":False})


@app.put("/institutions/{institution_id}/config/examples",response_model=ReplacementPreviewResponse,tags=["Institution Examples"],description="Previews or replaces all institution examples. Changed embeddings are refreshed; the index is not rebuilt automatically.")
async def replace_all_examples(institution_id: InstitutionId,payload: ExamplesPayload,request: Request,dry_run: bool=False,confirm: bool=False):
    store,manager=get_store(request),get_manager(request); impact=store.examples_replacement_impact(institution_id,payload)
    if impact["unknown_specific_ids"]: raise HTTPException(400,f"Unknown specific types: {', '.join(impact['unknown_specific_ids'])}")
    destructive=bool(impact["will_delete"]["examples"])
    response=ReplacementPreviewResponse(**impact,requires_confirmation=destructive,applied=False)
    if dry_run or (destructive and not confirm): return response
    await run_in_threadpool(store.replace_examples_selective,institution_id,payload)
    await run_in_threadpool(manager.sync_examples,institution_id); manager.invalidate(institution_id)
    return response.model_copy(update={"applied":True,"index_ready":False,"requires_rebuild":True,"requires_confirmation":False})


@app.post("/institutions/{institution_id}/config/rebuild-index", response_model=RebuildResponse, tags=["Institution Index Management"])
async def rebuild_index(institution_id: InstitutionId, request: Request):
    store, manager = get_store(request), get_manager(request)
    if not store.institution_exists(institution_id):
        raise HTTPException(404, "Classification configuration was not found for this institution")
    if not store.statistics(institution_id)["examples"]:
        raise HTTPException(409, "Classification index is not ready for this institution")
    stats = await run_in_threadpool(manager.rebuild, institution_id)
    classifier = manager.get(institution_id)
    return RebuildResponse(institution_id=institution_id,index_ready=True,requires_rebuild=False,statistics=stats,warnings=classifier.warnings)


async def run_classification(institution_id: str, payload: ClassifyRequest, request: Request, *, include_debug: bool) -> dict:
    store, manager = get_store(request), get_manager(request)
    if not store.institution_exists(institution_id):
        raise HTTPException(404, "Classification configuration was not found for this institution")
    stats = store.statistics(institution_id)
    if not stats["examples"]:
        raise HTTPException(409, "Classification index is not ready for this institution")
    try:
        classifier = await run_in_threadpool(manager.ensure_loaded, institution_id)
        return await run_in_threadpool(classifier.classify, payload.text, include_debug)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(409, "Classification index is not ready for this institution") from exc


@app.post("/institutions/{institution_id}/classify", response_model=ClassifyResponse, tags=["Institution Classification"], description="Production endpoint called by the Wathiq backend.")
async def classify(institution_id: InstitutionId, payload: ClassifyRequest, request: Request):
    result = await run_classification(institution_id, payload, request, include_debug=False)
    return ClassifyResponse(id=payload.id, broad_genre=result["broad_category"], specific_genre=result["specific_type"])


@app.post("/institutions/{institution_id}/classify/debug", response_model=DebugClassifyResponse, tags=["Development Debug"], description="Development diagnostics only; not for production backend use.")
async def classify_debug(institution_id: InstitutionId, payload: ClassifyRequest, request: Request):
    return DebugClassifyResponse(id=payload.id, **await run_classification(institution_id, payload, request, include_debug=True))


# Backward-compatible aliases are restricted to the configured default institution.
@app.get("/config/taxonomy", deprecated=True, tags=["Deprecated Default Institution"])
async def old_taxonomy(request: Request): return await taxonomy(settings.default_institution_id, request)
@app.get("/config/examples", deprecated=True, tags=["Deprecated Default Institution"])
async def old_examples(request: Request): return await examples(settings.default_institution_id, request)
@app.post("/config/import-definitions", response_model=ImportResponse, deprecated=True, tags=["Deprecated Default Institution"])
async def old_import_definitions(payload: DefinitionsPayload, request: Request): return await do_import_definitions(settings.default_institution_id,payload,request)
@app.post("/config/import-definitions-file", response_model=ImportResponse, deprecated=True, tags=["Deprecated Default Institution"])
async def old_import_definitions_file(request: Request,file: UploadFile=File(...)): return await do_import_definitions(settings.default_institution_id,DefinitionsPayload.model_validate(await parse_uploaded_json(file)),request)
@app.post("/config/import-examples", response_model=ImportResponse, deprecated=True, tags=["Deprecated Default Institution"])
async def old_import_examples(payload: ExamplesPayload,request: Request): return await do_import_examples(settings.default_institution_id,payload,request)
@app.post("/config/import-examples-file", response_model=ImportResponse, deprecated=True, tags=["Deprecated Default Institution"])
async def old_import_examples_file(request: Request,file: UploadFile=File(...)): return await do_import_examples(settings.default_institution_id,ExamplesPayload.model_validate(await parse_uploaded_json(file)),request)
@app.post("/config/broad", response_model=MutationResponse, deprecated=True, tags=["Deprecated Default Institution"])
async def old_upsert_broad(payload: SingleBroadUpsert,request: Request): return await upsert_broad(settings.default_institution_id,payload,request)
@app.post("/config/specific", response_model=MutationResponse, deprecated=True, tags=["Deprecated Default Institution"])
async def old_upsert_specific(payload: SingleSpecificUpsert,request: Request): return await upsert_specific(settings.default_institution_id,payload,request)
@app.post("/config/examples", response_model=MutationResponse, deprecated=True, tags=["Deprecated Default Institution"])
async def old_upsert_examples(payload: ExamplesUpsert,request: Request): return await upsert_examples(settings.default_institution_id,payload,request)
@app.post("/config/rebuild-index", response_model=RebuildResponse, deprecated=True, tags=["Deprecated Default Institution"])
async def old_rebuild(request: Request): return await rebuild_index(settings.default_institution_id,request)
@app.post("/classify", response_model=ClassifyResponse, deprecated=True, tags=["Deprecated Default Institution"])
async def old_classify(payload: ClassifyRequest,request: Request): return await classify(settings.default_institution_id,payload,request)
@app.post("/classify/debug", response_model=DebugClassifyResponse, deprecated=True, tags=["Deprecated Default Institution"])
async def old_classify_debug(payload: ClassifyRequest,request: Request): return await classify_debug(settings.default_institution_id,payload,request)
