import json
import sqlite3
from pathlib import Path

from app.database import SQLiteStore
from app.schemas import DefinitionsPayload, ExamplesPayload

ROOT=Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT/"data"/"multi_tenant_test"/name).read_text(encoding="utf-8"))


def test_two_institutions_are_isolated_and_persisted(tmp_path):
    path=tmp_path/"classifier.db"
    store=SQLiteStore(path)
    da=DefinitionsPayload.model_validate(load("institution_a_definitions.json"))
    db=DefinitionsPayload.model_validate(load("institution_b_definitions.json"))
    ea=ExamplesPayload.model_validate(load("institution_a_examples.json"))
    eb=ExamplesPayload.model_validate(load("institution_b_examples.json"))
    store.replace_definitions("institution_a",da)
    store.replace_definitions("institution_b",db)
    store.replace_examples("institution_a",ea)
    store.replace_examples("institution_b",eb)
    assert store.taxonomy("institution_a")["broad_categories"][0]["broad_category"]=="AdministrativeAndOrganizational"
    assert store.taxonomy("institution_b")["broad_categories"][0]["broad_category"]=="FinancialAndAccounting"
    assert {r["id"] for r in store.list_examples("institution_a")}=={e.id for e in ea.examples}
    assert {r["id"] for r in store.list_examples("institution_b")}=={e.id for e in eb.examples}
    before=store.statistics("institution_b")
    store.replace_examples("institution_a",ea)
    assert store.statistics("institution_b")==before
    store.close()
    reopened=SQLiteStore(path)
    assert reopened.statistics("institution_a")["examples"]==6
    assert reopened.statistics("institution_b")["examples"]==6
    reopened.close()


def test_legacy_database_is_backed_up_and_migrated_idempotently(tmp_path):
    path=tmp_path/"legacy.db"
    conn=sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE broad_categories(id TEXT PRIMARY KEY,name_ar TEXT NOT NULL,name_en TEXT NOT NULL,definition_ar TEXT NOT NULL,definition_en TEXT NOT NULL,is_active INTEGER NOT NULL,sort_order INTEGER NOT NULL,updated_at TEXT NOT NULL);
    CREATE TABLE specific_types(id TEXT PRIMARY KEY,broad_id TEXT NOT NULL,name_ar TEXT NOT NULL,name_en TEXT NOT NULL,definition_ar TEXT NOT NULL,definition_en TEXT NOT NULL,is_active INTEGER NOT NULL,sort_order INTEGER NOT NULL,updated_at TEXT NOT NULL);
    CREATE TABLE examples(id TEXT PRIMARY KEY,broad_id TEXT NOT NULL,specific_id TEXT NOT NULL,text TEXT NOT NULL,language TEXT NOT NULL,source TEXT NOT NULL,length_group TEXT,char_count INTEGER,text_hash TEXT NOT NULL,updated_at TEXT NOT NULL);
    CREATE TABLE embeddings(entity_kind TEXT NOT NULL,entity_id TEXT NOT NULL,model_key TEXT NOT NULL,text_hash TEXT NOT NULL,dimension INTEGER NOT NULL,vector BLOB NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(entity_kind,entity_id,model_key));
    CREATE TABLE service_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    INSERT INTO broad_categories VALUES('LegacyBroad','قديم','Legacy','تعريف قديم صالح','Valid legacy definition',1,0,'2026-01-01');
    """)
    conn.commit(); conn.close()
    store=SQLiteStore(path,"tenant-default")
    assert store.institution_exists("tenant-default")
    assert store.statistics("tenant-default")["broad_categories"]==1
    assert path.with_suffix(".db.pre_multitenant.bak").exists()
    store.close()
    again=SQLiteStore(path,"tenant-default")
    assert again.statistics("tenant-default")["broad_categories"]==1
    again.close()


def test_composite_keys_allow_same_ids_in_different_institutions(tmp_path):
    store=SQLiteStore(tmp_path/"same.db")
    definitions=DefinitionsPayload.model_validate(load("institution_a_definitions.json"))
    store.replace_definitions("a",definitions)
    store.replace_definitions("b",definitions)
    assert store.statistics("a")["specific_types"]==2
    assert store.statistics("b")["specific_types"]==2
    store.close()
