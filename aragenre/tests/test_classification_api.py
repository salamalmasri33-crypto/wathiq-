from fastapi.testclient import TestClient

from app.main import app


class FakeClassifier:
    ready = True
    last_error = None
    warnings = []
    def classify(self, text: str, debug: bool = False) -> dict:
        result = {"broad_category":"AdministrativeAndOrganizational","broad_category_ar":"إداري وتنظيمي","specific_type":"AdministrativeDecision","specific_type_ar":"قرار إداري","model_pipeline":"V10 Broad + V18 Specific K20"}
        if debug:
            result["debug"]={"broad_candidates":[{"id":"AdministrativeAndOrganizational","name_ar":"إداري","final_score":1.5,"example_score":1.2,"definition_score":1.1,"nearest_example_ids":["a1"]}],"specific_candidates":[{"id":"AdministrativeDecision","name_ar":"قرار","rrf_score":.08,"e5_rank":1,"arabic_rank":1,"bm25_rank":1}],"text_chars_used":len(text)}
        return result


class FakeStore:
    def institution_exists(self, institution_id): return institution_id != "missing"
    def statistics(self, institution_id): return {"broad_categories":1,"specific_types":1,"examples":0 if institution_id == "not-ready" else 3,"embeddings":5}


class FakeManager:
    def __init__(self): self.classifier=FakeClassifier()
    def ensure_loaded(self, institution_id): return self.classifier


client=TestClient(app)
app.state.store=FakeStore()
app.state.manager=FakeManager()


def test_classify_returns_only_backend_contract_and_same_id():
    response=client.post("/institutions/institution_a/classify",json={"id":"document_123","text":"قرار إداري بتشكيل لجنة"})
    assert response.status_code==200
    assert response.json()=={"id":"document_123","broad_genre":"AdministrativeAndOrganizational","specific_genre":"AdministrativeDecision"}


def test_classify_debug_returns_full_details():
    response=client.post("/institutions/institution_a/classify/debug",json={"id":"document_123","text":"قرار إداري بتشكيل لجنة"})
    assert response.status_code==200
    body=response.json()
    assert {"id","broad_category","broad_category_ar","specific_type","specific_type_ar","model_pipeline","debug"}==set(body)
    assert body["debug"]["broad_candidates"][0]["nearest_example_ids"]
    assert body["debug"]["specific_candidates"][0]["rrf_score"]


def test_blank_fields_return_422():
    assert client.post("/institutions/institution_a/classify",json={"id":" ","text":"نص صالح"}).status_code==422
    assert client.post("/institutions/institution_a/classify",json={"id":"doc","text":" "}).status_code==422


def test_missing_and_not_ready_institutions():
    payload={"id":"doc","text":"نص صالح"}
    assert client.post("/institutions/missing/classify",json=payload).status_code==404
    assert client.post("/institutions/not-ready/classify",json=payload).status_code==409


def test_institution_id_rejects_path_traversal_characters():
    assert client.post("/institutions/bad%2F..%2Fid/classify",json={"id":"doc","text":"نص"}).status_code in {404,422}
    assert client.post("/institutions/bad%20id/classify",json={"id":"doc","text":"نص"}).status_code==422


def test_new_routes_and_deprecated_aliases_are_documented():
    paths=app.openapi()["paths"]
    new=["config/status","config/taxonomy","config/examples","config/import-definitions","config/import-definitions-file","config/import-examples","config/import-examples-file","config/broad","config/specific","config/rebuild-index","classify","classify/debug"]
    assert all(f"/institutions/{{institution_id}}/{suffix}" in paths for suffix in new)
    assert paths["/classify"]["post"]["deprecated"] is True


def test_patch_schemas_reject_empty_requests_and_openapi_has_models():
    from app.schemas import BroadPatch, ExamplePatch, SpecificPatch
    import pytest
    for schema in (BroadPatch,SpecificPatch,ExamplePatch):
        with pytest.raises(Exception): schema.model_validate({})
    paths=app.openapi()["paths"]
    operations=[
        paths["/institutions/{institution_id}/config/broad/{broad_id}"]["patch"],
        paths["/institutions/{institution_id}/config/broad/{broad_id}"]["delete"],
        paths["/institutions/{institution_id}/config/examples/{example_id}"]["delete"],
        paths["/institutions/{institution_id}/config/taxonomy"]["put"],
    ]
    assert all(operation["responses"]["200"]["content"]["application/json"]["schema"].get("$ref") for operation in operations)
