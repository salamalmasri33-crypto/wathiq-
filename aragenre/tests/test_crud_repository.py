import json
from pathlib import Path

import numpy as np
import pytest

from app.database import SQLiteStore
from app.schemas import DefinitionsPayload, ExamplesPayload

ROOT=Path(__file__).resolve().parents[1]


def load(name,model):
    return model.model_validate(json.loads((ROOT/"data"/"multi_tenant_test"/name).read_text(encoding="utf-8")))


@pytest.fixture
def configured(tmp_path):
    store=SQLiteStore(tmp_path/"crud.db")
    definitions=load("institution_a_definitions.json",DefinitionsPayload)
    examples=load("institution_a_examples.json",ExamplesPayload)
    for tenant in ("a","b"):
        store.replace_definitions(tenant,definitions); store.replace_examples(tenant,examples)
    yield store,definitions,examples
    store.close()


def add_embeddings(store,tenant):
    vector=np.array([1,0],dtype=np.float32)
    for row in store.list_broad(tenant,False): store.save_embedding(tenant,"broad_definition",row["id"],"model","hash",vector)
    for row in store.list_specific(tenant,False): store.save_embedding(tenant,"specific_definition",row["id"],"model","hash",vector)
    for row in store.list_examples(tenant,False): store.save_embedding(tenant,"example",row["id"],"model","hash",vector)


def test_patch_broad_and_specific_are_tenant_scoped(configured):
    store,_,_=configured
    assert store.patch_broad("a","AdministrativeAndOrganizational",{"name_en":"Changed"})
    assert store.get_broad("a","AdministrativeAndOrganizational")["name_en"]=="Changed"
    assert store.get_broad("b","AdministrativeAndOrganizational")["name_en"]!="Changed"
    assert store.patch_specific("a","AdministrativeDecision",{"definition_en":"A changed definition"})
    assert store.get_specific("a","AdministrativeDecision")["definition_en"]=="A changed definition"
    assert store.get_specific("b","AdministrativeDecision")["definition_en"]!="A changed definition"


def test_patch_example_invalidates_only_its_embeddings(configured):
    store,_,_=configured; add_embeddings(store,"a")
    before=store.statistics("a")["embeddings"]
    store.patch_example("a","a_decision_1",{"text":"نص جديد طويل بما يكفي لاختبار تحديث المثال الإداري"})
    assert store.statistics("a")["embeddings"]==before-1
    assert store.get_embedding("a","example","a_decision_2","model","hash") is not None


def test_broad_impact_and_confirmation_data(configured):
    store,_,_=configured; add_embeddings(store,"a")
    impact=store.broad_deletion_impact("a","AdministrativeAndOrganizational")
    assert impact=={"specific_types":2,"examples":6,"embeddings":9}
    store.upsert_broad("a",{"broad_category":"EmptyBroad","name_ar":"فارغ","name_en":"Empty","definition_ar":"تعريف عربي كاف للتصنيف","definition_en":"A sufficient empty definition","is_active":True})
    assert store.broad_deletion_impact("a","EmptyBroad")["specific_types"]==0


def test_cascade_broad_delete_removes_dependencies_only_from_a(configured):
    store,_,_=configured; add_embeddings(store,"a"); add_embeddings(store,"b")
    counts=store.delete_broad("a","AdministrativeAndOrganizational")
    assert counts=={"broad_categories":1,"specific_types":2,"examples":6,"embeddings":9}
    assert store.statistics("a")["broad_categories"]==0
    assert store.statistics("b")["broad_categories"]==1
    assert store.statistics("b")["examples"]==6


def test_specific_impact_and_cascade_delete(configured):
    store,_,_=configured; add_embeddings(store,"a")
    impact=store.specific_deletion_impact("a","AdministrativeDecision")
    assert impact=={"examples":3,"embeddings":4}
    counts=store.delete_specific("a","AdministrativeDecision")
    assert counts=={"specific_types":1,"examples":3,"embeddings":4}
    assert store.get_specific("a","AdministrativeDecision") is None
    assert store.statistics("b")["examples"]==6


def test_delete_example_removes_its_embedding(configured):
    store,_,_=configured; add_embeddings(store,"a"); before=store.statistics("a")["embeddings"]
    assert store.delete_example("a","a_decision_1")
    assert store.get_example("a","a_decision_1") is None
    assert store.statistics("a")["embeddings"]==before-1


def test_taxonomy_preview_and_replacement_are_scoped(configured):
    store,_,_=configured
    replacement=load("institution_b_definitions.json",DefinitionsPayload)
    impact=store.taxonomy_replacement_impact("a",replacement)
    assert impact["will_delete"]=={"broad_categories":1,"specific_types":2,"examples":6}
    assert store.taxonomy("a")["broad_categories"][0]["broad_category"]=="AdministrativeAndOrganizational"
    store.replace_taxonomy("a",replacement)
    assert store.taxonomy("a")["broad_categories"][0]["broad_category"]=="FinancialAndAccounting"
    assert store.taxonomy("b")["broad_categories"][0]["broad_category"]=="AdministrativeAndOrganizational"


def test_examples_preview_and_selective_replacement(configured):
    store,_,examples=configured
    reduced=ExamplesPayload(examples=examples.examples[:3])
    impact=store.examples_replacement_impact("a",reduced)
    assert impact["will_delete"]["examples"]==3
    assert store.statistics("a")["examples"]==6
    store.replace_examples_selective("a",reduced)
    assert store.statistics("a")["examples"]==3
    assert store.statistics("b")["examples"]==6


def test_inactive_broad_excludes_its_specific_types(configured):
    store,_,_=configured
    store.patch_broad("a","AdministrativeAndOrganizational",{"is_active":False})
    assert store.list_broad("a",True)==[]
    assert store.list_specific("a",True)==[]
    assert store.list_examples("a",True)==[]


def test_cascade_transaction_rolls_back_on_failure(configured):
    store,_,_=configured; add_embeddings(store,"a"); before=store.statistics("a")
    with store.transaction() as conn:
        conn.execute("CREATE TRIGGER fail_broad_delete BEFORE DELETE ON broad_categories WHEN OLD.institution_id='a' BEGIN SELECT RAISE(ABORT,'forced'); END")
    with pytest.raises(Exception): store.delete_broad("a","AdministrativeAndOrganizational")
    assert store.statistics("a")==before
