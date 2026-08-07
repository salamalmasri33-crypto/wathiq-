from __future__ import annotations

import hashlib
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from .schemas import DefinitionsPayload, ExampleRecord, ExamplesPayload


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SQLiteStore:
    TABLES = ("broad_categories", "specific_types", "examples", "embeddings")

    def __init__(self, path: Path, default_institution_id: str = "default-institution"):
        self.path = Path(path)
        self.default_institution_id = default_institution_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._initialize()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                self._connection.execute("BEGIN")
                yield self._connection
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def _columns(self, table: str) -> set[str]:
        return {row["name"] for row in self._connection.execute(f"PRAGMA table_info({table})")}

    def _initialize(self) -> None:
        legacy = bool(self._columns("broad_categories")) and "institution_id" not in self._columns("broad_categories")
        if legacy:
            backup_path = self.path.with_suffix(self.path.suffix + ".pre_multitenant.bak")
            if not backup_path.exists():
                destination = sqlite3.connect(backup_path)
                try:
                    self._connection.backup(destination)
                finally:
                    destination.close()
            self._migrate_legacy()
        self._create_schema()

    def _create_schema(self) -> None:
        with self.transaction() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS broad_categories (
                    institution_id TEXT NOT NULL, id TEXT NOT NULL,
                    name_ar TEXT NOT NULL, name_en TEXT NOT NULL,
                    definition_ar TEXT NOT NULL, definition_en TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL,
                    PRIMARY KEY (institution_id, id)
                );
                CREATE TABLE IF NOT EXISTS specific_types (
                    institution_id TEXT NOT NULL, id TEXT NOT NULL, broad_id TEXT NOT NULL,
                    name_ar TEXT NOT NULL, name_en TEXT NOT NULL,
                    definition_ar TEXT NOT NULL, definition_en TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL,
                    PRIMARY KEY (institution_id, id),
                    FOREIGN KEY (institution_id, broad_id)
                        REFERENCES broad_categories(institution_id, id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS examples (
                    institution_id TEXT NOT NULL, id TEXT NOT NULL,
                    broad_id TEXT NOT NULL, specific_id TEXT NOT NULL, text TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'ar', source TEXT NOT NULL DEFAULT 'admin',
                    length_group TEXT, char_count INTEGER, text_hash TEXT NOT NULL,
                    updated_at TEXT NOT NULL, PRIMARY KEY (institution_id, id),
                    FOREIGN KEY (institution_id, broad_id)
                        REFERENCES broad_categories(institution_id, id) ON DELETE CASCADE,
                    FOREIGN KEY (institution_id, specific_id)
                        REFERENCES specific_types(institution_id, id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS embeddings (
                    institution_id TEXT NOT NULL, entity_kind TEXT NOT NULL,
                    entity_id TEXT NOT NULL, model_key TEXT NOT NULL, text_hash TEXT NOT NULL,
                    dimension INTEGER NOT NULL, vector BLOB NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY (institution_id, entity_kind, entity_id, model_key)
                );
                CREATE TABLE IF NOT EXISTS service_metadata (
                    institution_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                    PRIMARY KEY (institution_id, key)
                );
                CREATE INDEX IF NOT EXISTS idx_specific_institution_broad
                    ON specific_types(institution_id, broad_id);
                CREATE INDEX IF NOT EXISTS idx_examples_institution_broad
                    ON examples(institution_id, broad_id);
                CREATE INDEX IF NOT EXISTS idx_examples_institution_specific
                    ON examples(institution_id, specific_id);
                """
            )

    def _migrate_legacy(self) -> None:
        institution = self.default_institution_id
        with self._lock:
            conn = self._connection
            conn.execute("PRAGMA foreign_keys = OFF")
            try:
                conn.execute("BEGIN")
                for table in (*self.TABLES, "service_metadata"):
                    conn.execute(f"ALTER TABLE {table} RENAME TO legacy_{table}")
                conn.commit()
                self._create_schema()
                conn.execute("BEGIN")
                conn.execute("INSERT INTO broad_categories SELECT ?, * FROM legacy_broad_categories", (institution,))
                conn.execute("INSERT INTO specific_types SELECT ?, * FROM legacy_specific_types", (institution,))
                conn.execute("INSERT INTO examples SELECT ?, * FROM legacy_examples", (institution,))
                conn.execute("INSERT INTO embeddings SELECT ?, * FROM legacy_embeddings", (institution,))
                conn.execute("INSERT INTO service_metadata SELECT ?, * FROM legacy_service_metadata", (institution,))
                for table in ("examples", "specific_types", "broad_categories", "embeddings", "service_metadata"):
                    conn.execute(f"DROP TABLE legacy_{table}")
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.execute("PRAGMA foreign_keys = ON")

    def institution_exists(self, institution_id: str) -> bool:
        with self._lock:
            return self._connection.execute(
                "SELECT 1 FROM broad_categories WHERE institution_id=? LIMIT 1", (institution_id,)
            ).fetchone() is not None

    def configured_institutions(self) -> int:
        with self._lock:
            return int(self._connection.execute("SELECT COUNT(DISTINCT institution_id) FROM broad_categories").fetchone()[0])

    def replace_definitions(self, institution_id: str, payload: DefinitionsPayload) -> dict[str, int]:
        now = utc_now()
        with self.transaction() as conn:
            conn.execute("DELETE FROM embeddings WHERE institution_id=?", (institution_id,))
            conn.execute("DELETE FROM examples WHERE institution_id=?", (institution_id,))
            conn.execute("DELETE FROM specific_types WHERE institution_id=?", (institution_id,))
            conn.execute("DELETE FROM broad_categories WHERE institution_id=?", (institution_id,))
            count = 0
            for broad_order, broad in enumerate(payload.broad_categories):
                conn.execute("INSERT INTO broad_categories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (institution_id, broad.broad_category, broad.name_ar, broad.name_en, broad.definition_ar, broad.definition_en, int(broad.is_active), broad_order, now))
                for specific_order, specific in enumerate(broad.specific_types):
                    conn.execute("INSERT INTO specific_types VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (institution_id, specific.specific_type, broad.broad_category, specific.name_ar, specific.name_en, specific.definition_ar, specific.definition_en, int(specific.is_active), specific_order, now))
                    count += 1
            conn.execute("INSERT INTO service_metadata VALUES (?, 'definitions_schema_version', ?) ON CONFLICT(institution_id,key) DO UPDATE SET value=excluded.value", (institution_id, payload.schema_version))
            conn.execute("INSERT INTO service_metadata VALUES (?, 'last_updated', ?) ON CONFLICT(institution_id,key) DO UPDATE SET value=excluded.value", (institution_id, now))
        return {"broad_categories": len(payload.broad_categories), "specific_types": count}

    def upsert_broad(self, institution_id: str, broad: dict[str, Any]) -> None:
        now = utc_now()
        with self.transaction() as conn:
            conn.execute("""INSERT INTO broad_categories
                (institution_id,id,name_ar,name_en,definition_ar,definition_en,is_active,sort_order,updated_at)
                VALUES (?,?,?,?,?,?,?,COALESCE((SELECT sort_order FROM broad_categories WHERE institution_id=? AND id=?),(SELECT COALESCE(MAX(sort_order),-1)+1 FROM broad_categories WHERE institution_id=?)),?)
                ON CONFLICT(institution_id,id) DO UPDATE SET name_ar=excluded.name_ar,name_en=excluded.name_en,definition_ar=excluded.definition_ar,definition_en=excluded.definition_en,is_active=excluded.is_active,updated_at=excluded.updated_at""",
                (institution_id,broad["broad_category"],broad["name_ar"],broad["name_en"],broad["definition_ar"],broad["definition_en"],int(broad.get("is_active",True)),institution_id,broad["broad_category"],institution_id,now))
            conn.execute("DELETE FROM embeddings WHERE institution_id=? AND entity_kind='broad_definition' AND entity_id=?", (institution_id,broad["broad_category"]))

    def upsert_specific(self, institution_id: str, broad_id: str, specific: dict[str, Any]) -> None:
        if not self.get_broad(institution_id, broad_id):
            raise ValueError(f"Unknown broad category: {broad_id}")
        now = utc_now()
        with self.transaction() as conn:
            conn.execute("""INSERT INTO specific_types
                (institution_id,id,broad_id,name_ar,name_en,definition_ar,definition_en,is_active,sort_order,updated_at)
                VALUES (?,?,?,?,?,?,?,?,COALESCE((SELECT sort_order FROM specific_types WHERE institution_id=? AND id=?),(SELECT COALESCE(MAX(sort_order),-1)+1 FROM specific_types WHERE institution_id=? AND broad_id=?)),?)
                ON CONFLICT(institution_id,id) DO UPDATE SET broad_id=excluded.broad_id,name_ar=excluded.name_ar,name_en=excluded.name_en,definition_ar=excluded.definition_ar,definition_en=excluded.definition_en,is_active=excluded.is_active,updated_at=excluded.updated_at""",
                (institution_id,specific["specific_type"],broad_id,specific["name_ar"],specific["name_en"],specific["definition_ar"],specific["definition_en"],int(specific.get("is_active",True)),institution_id,specific["specific_type"],institution_id,broad_id,now))
            conn.execute("DELETE FROM embeddings WHERE institution_id=? AND entity_kind='specific_definition' AND entity_id=?", (institution_id,specific["specific_type"]))

    def replace_examples(self, institution_id: str, payload: ExamplesPayload) -> dict[str, int]:
        self._validate_examples(institution_id, payload.examples)
        with self.transaction() as conn:
            conn.execute("DELETE FROM embeddings WHERE institution_id=? AND entity_kind='example'", (institution_id,))
            conn.execute("DELETE FROM examples WHERE institution_id=?", (institution_id,))
            self._insert_examples(conn, institution_id, payload.examples, upsert=False)
        return {"examples": len(payload.examples)}

    def upsert_examples(self, institution_id: str, examples: list[ExampleRecord]) -> dict[str, int]:
        self._validate_examples(institution_id, examples)
        with self.transaction() as conn:
            self._insert_examples(conn, institution_id, examples, upsert=True)
            for item in examples:
                conn.execute("DELETE FROM embeddings WHERE institution_id=? AND entity_kind='example' AND entity_id=?", (institution_id,item.id))
        return {"examples": len(examples)}

    def _insert_examples(self, conn: sqlite3.Connection, institution_id: str, examples: list[ExampleRecord], upsert: bool) -> None:
        suffix = " ON CONFLICT(institution_id,id) DO UPDATE SET broad_id=excluded.broad_id,specific_id=excluded.specific_id,text=excluded.text,language=excluded.language,source=excluded.source,length_group=excluded.length_group,char_count=excluded.char_count,text_hash=excluded.text_hash,updated_at=excluded.updated_at" if upsert else ""
        for item in examples:
            conn.execute("INSERT INTO examples VALUES (?,?,?,?,?,?,?,?,?,?,?)" + suffix,
                (institution_id,item.id,item.broad_category,item.specific_type,item.text,item.language,item.source,item.length_group,item.char_count or len(item.text),text_hash(item.text),utc_now()))

    def _validate_examples(self, institution_id: str, examples: list[ExampleRecord]) -> None:
        broad_ids = {r["id"] for r in self.list_broad(institution_id, False)}
        specifics = {r["id"]: r["broad_id"] for r in self.list_specific(institution_id, False)}
        for item in examples:
            if item.broad_category not in broad_ids:
                raise ValueError(f"Example {item.id} refers to unknown broad category {item.broad_category}")
            if item.specific_type not in specifics:
                raise ValueError(f"Example {item.id} refers to unknown specific type {item.specific_type}")
            if specifics[item.specific_type] != item.broad_category:
                raise ValueError(f"Example {item.id} has an invalid broad/specific hierarchy")

    def get_broad(self, institution_id: str, broad_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute("SELECT * FROM broad_categories WHERE institution_id=? AND id=?", (institution_id,broad_id)).fetchone()
        return dict(row) if row else None

    def list_broad(self, institution_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        sql = "SELECT * FROM broad_categories WHERE institution_id=?" + (" AND is_active=1" if active_only else "") + " ORDER BY sort_order,id"
        with self._lock:
            return [dict(r) for r in self._connection.execute(sql,(institution_id,)).fetchall()]

    def get_specific(self, institution_id: str, specific_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute("SELECT * FROM specific_types WHERE institution_id=? AND id=?", (institution_id, specific_id)).fetchone()
        return dict(row) if row else None

    def list_specific(self, institution_id: str, active_only: bool = True, broad_id: str | None = None) -> list[dict[str, Any]]:
        if active_only:
            sql = "SELECT s.* FROM specific_types s JOIN broad_categories b ON b.institution_id=s.institution_id AND b.id=s.broad_id WHERE s.institution_id=? AND s.is_active=1 AND b.is_active=1 ORDER BY s.broad_id,s.sort_order,s.id"
        else:
            sql = "SELECT * FROM specific_types WHERE institution_id=? ORDER BY broad_id,sort_order,id"
        params: list[Any] = [institution_id]
        if broad_id is not None:
            sql = sql.replace(" ORDER BY", " AND " + ("s.broad_id" if active_only else "broad_id") + "=? ORDER BY")
            params.append(broad_id)
        with self._lock:
            return [dict(r) for r in self._connection.execute(sql,params).fetchall()]

    def get_example(self, institution_id: str, example_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute("SELECT * FROM examples WHERE institution_id=? AND id=?", (institution_id, example_id)).fetchone()
        return dict(row) if row else None

    def list_examples(self, institution_id: str, active_only: bool = True, broad_id: str | None = None, specific_id: str | None = None, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
        sql = """SELECT e.* FROM examples e JOIN broad_categories b ON b.institution_id=e.institution_id AND b.id=e.broad_id JOIN specific_types s ON s.institution_id=e.institution_id AND s.id=e.specific_id WHERE e.institution_id=?"""
        params: list[Any] = [institution_id]
        if active_only: sql += " AND b.is_active=1 AND s.is_active=1"
        if broad_id is not None: sql += " AND e.broad_id=?"; params.append(broad_id)
        if specific_id is not None: sql += " AND e.specific_id=?"; params.append(specific_id)
        sql += " ORDER BY e.broad_id,e.specific_id,e.id"
        if limit is not None: sql += " LIMIT ? OFFSET ?"; params.extend([limit, offset])
        with self._lock:
            return [dict(r) for r in self._connection.execute(sql,params).fetchall()]

    def broad_detail(self, institution_id: str, broad_id: str) -> dict[str, Any] | None:
        broad = self.get_broad(institution_id, broad_id)
        if not broad: return None
        with self._lock:
            counts=self._connection.execute("SELECT (SELECT COUNT(*) FROM specific_types WHERE institution_id=? AND broad_id=?),(SELECT COUNT(*) FROM examples WHERE institution_id=? AND broad_id=?)",(institution_id,broad_id,institution_id,broad_id)).fetchone()
        return {**broad,"specific_count":int(counts[0]),"example_count":int(counts[1])}

    def patch_broad(self, institution_id: str, broad_id: str, changes: dict[str, Any]) -> bool:
        if not self.get_broad(institution_id,broad_id): return False
        allowed={"name_ar","name_en","definition_ar","definition_en","is_active"}
        values={k:(int(v) if k=="is_active" else v) for k,v in changes.items() if k in allowed}
        with self.transaction() as conn:
            assignments=",".join(f"{key}=?" for key in values)
            conn.execute(f"UPDATE broad_categories SET {assignments},updated_at=? WHERE institution_id=? AND id=?",(*values.values(),utc_now(),institution_id,broad_id))
            if {"definition_ar","definition_en"} & values.keys():
                conn.execute("DELETE FROM embeddings WHERE institution_id=? AND entity_kind='broad_definition' AND entity_id=?",(institution_id,broad_id))
        return True

    def patch_specific(self, institution_id: str, specific_id: str, changes: dict[str, Any]) -> bool:
        current=self.get_specific(institution_id,specific_id)
        if not current: return False
        broad_id=changes.get("broad_id",current["broad_id"])
        if not self.get_broad(institution_id,broad_id): raise ValueError(f"Unknown broad category: {broad_id}")
        allowed={"broad_id","name_ar","name_en","definition_ar","definition_en","is_active"}
        values={k:(int(v) if k=="is_active" else v) for k,v in changes.items() if k in allowed}
        with self.transaction() as conn:
            assignments=",".join(f"{key}=?" for key in values)
            conn.execute(f"UPDATE specific_types SET {assignments},updated_at=? WHERE institution_id=? AND id=?",(*values.values(),utc_now(),institution_id,specific_id))
            if broad_id != current["broad_id"]:
                conn.execute("UPDATE examples SET broad_id=?,updated_at=? WHERE institution_id=? AND specific_id=?",(broad_id,utc_now(),institution_id,specific_id))
            if {"broad_id","definition_ar","definition_en"} & values.keys():
                conn.execute("DELETE FROM embeddings WHERE institution_id=? AND entity_kind='specific_definition' AND entity_id=?",(institution_id,specific_id))
        return True

    def patch_example(self, institution_id: str, example_id: str, changes: dict[str, Any]) -> bool:
        current=self.get_example(institution_id,example_id)
        if not current: return False
        specific_id=changes.get("specific_id",current["specific_id"])
        specific=self.get_specific(institution_id,specific_id)
        if not specific: raise ValueError(f"Unknown specific type: {specific_id}")
        mapping={"specific_id":specific_id,"broad_id":specific["broad_id"],"text":changes.get("text",current["text"]),"language":changes.get("language",current["language"]),"source":changes.get("source",current["source"]),"length_group":changes.get("length_group",current["length_group"])}
        mapping["char_count"]=len(mapping["text"]); mapping["text_hash"]=text_hash(mapping["text"])
        with self.transaction() as conn:
            conn.execute("UPDATE examples SET broad_id=?,specific_id=?,text=?,language=?,source=?,length_group=?,char_count=?,text_hash=?,updated_at=? WHERE institution_id=? AND id=?",(mapping["broad_id"],mapping["specific_id"],mapping["text"],mapping["language"],mapping["source"],mapping["length_group"],mapping["char_count"],mapping["text_hash"],utc_now(),institution_id,example_id))
            conn.execute("DELETE FROM embeddings WHERE institution_id=? AND entity_kind='example' AND entity_id=?",(institution_id,example_id))
        return True

    def broad_deletion_impact(self, institution_id: str, broad_id: str) -> dict[str,int] | None:
        if not self.get_broad(institution_id,broad_id): return None
        with self._lock:
            specifics=[r[0] for r in self._connection.execute("SELECT id FROM specific_types WHERE institution_id=? AND broad_id=?",(institution_id,broad_id))]
            examples=[r[0] for r in self._connection.execute("SELECT id FROM examples WHERE institution_id=? AND broad_id=?",(institution_id,broad_id))]
            ids=[broad_id,*specifics,*examples]
            placeholders=",".join("?" for _ in ids)
            embeddings=int(self._connection.execute(f"SELECT COUNT(*) FROM embeddings WHERE institution_id=? AND entity_id IN ({placeholders})",(institution_id,*ids)).fetchone()[0])
        return {"specific_types":len(specifics),"examples":len(examples),"embeddings":embeddings}

    def specific_deletion_impact(self, institution_id: str, specific_id: str) -> dict[str,int] | None:
        if not self.get_specific(institution_id,specific_id): return None
        with self._lock:
            examples=[r[0] for r in self._connection.execute("SELECT id FROM examples WHERE institution_id=? AND specific_id=?",(institution_id,specific_id))]
            ids=[specific_id,*examples]; placeholders=",".join("?" for _ in ids)
            embeddings=int(self._connection.execute(f"SELECT COUNT(*) FROM embeddings WHERE institution_id=? AND entity_id IN ({placeholders})",(institution_id,*ids)).fetchone()[0])
        return {"examples":len(examples),"embeddings":embeddings}

    def delete_broad(self, institution_id: str, broad_id: str) -> dict[str,int]:
        impact=self.broad_deletion_impact(institution_id,broad_id)
        if impact is None: raise KeyError(broad_id)
        with self.transaction() as conn:
            specifics=[r[0] for r in conn.execute("SELECT id FROM specific_types WHERE institution_id=? AND broad_id=?",(institution_id,broad_id))]
            examples=[r[0] for r in conn.execute("SELECT id FROM examples WHERE institution_id=? AND broad_id=?",(institution_id,broad_id))]
            ids=[broad_id,*specifics,*examples]; placeholders=",".join("?" for _ in ids)
            conn.execute(f"DELETE FROM embeddings WHERE institution_id=? AND entity_id IN ({placeholders})",(institution_id,*ids))
            conn.execute("DELETE FROM broad_categories WHERE institution_id=? AND id=?",(institution_id,broad_id))
        return {"broad_categories":1,**impact}

    def delete_specific(self, institution_id: str, specific_id: str) -> dict[str,int]:
        impact=self.specific_deletion_impact(institution_id,specific_id)
        if impact is None: raise KeyError(specific_id)
        with self.transaction() as conn:
            examples=[r[0] for r in conn.execute("SELECT id FROM examples WHERE institution_id=? AND specific_id=?",(institution_id,specific_id))]
            ids=[specific_id,*examples]; placeholders=",".join("?" for _ in ids)
            conn.execute(f"DELETE FROM embeddings WHERE institution_id=? AND entity_id IN ({placeholders})",(institution_id,*ids))
            conn.execute("DELETE FROM specific_types WHERE institution_id=? AND id=?",(institution_id,specific_id))
        return {"specific_types":1,**impact}

    def delete_example(self, institution_id: str, example_id: str) -> bool:
        if not self.get_example(institution_id,example_id): return False
        with self.transaction() as conn:
            conn.execute("DELETE FROM embeddings WHERE institution_id=? AND entity_kind='example' AND entity_id=?",(institution_id,example_id))
            conn.execute("DELETE FROM examples WHERE institution_id=? AND id=?",(institution_id,example_id))
        return True

    def taxonomy_replacement_impact(self, institution_id: str, payload: DefinitionsPayload) -> dict[str,dict[str,int]]:
        old_broad={r["id"] for r in self.list_broad(institution_id,False)}
        old_specific={r["id"] for r in self.list_specific(institution_id,False)}
        new_broad={b.broad_category for b in payload.broad_categories}
        new_specific={s.specific_type for b in payload.broad_categories for s in b.specific_types}
        with self._lock:
            orphan_examples=int(self._connection.execute("SELECT COUNT(*) FROM examples WHERE institution_id=? AND specific_id NOT IN ({})".format(",".join("?" for _ in new_specific)),(institution_id,*new_specific)).fetchone()[0])
        return {"will_replace":{"broad_categories":len(new_broad),"specific_types":len(new_specific)},"will_delete":{"broad_categories":len(old_broad-new_broad),"specific_types":len(old_specific-new_specific),"examples":orphan_examples}}

    def replace_taxonomy(self, institution_id: str, payload: DefinitionsPayload) -> dict[str,int]:
        impact=self.taxonomy_replacement_impact(institution_id,payload)
        now=utc_now(); new_broad={b.broad_category for b in payload.broad_categories}; new_specific={s.specific_type for b in payload.broad_categories for s in b.specific_types}
        with self.transaction() as conn:
            orphan_ids=[r[0] for r in conn.execute("SELECT id FROM examples WHERE institution_id=? AND specific_id NOT IN ({})".format(",".join("?" for _ in new_specific)),(institution_id,*new_specific))]
            if orphan_ids:
                ph=",".join("?" for _ in orphan_ids); conn.execute(f"DELETE FROM embeddings WHERE institution_id=? AND entity_kind='example' AND entity_id IN ({ph})",(institution_id,*orphan_ids)); conn.execute(f"DELETE FROM examples WHERE institution_id=? AND id IN ({ph})",(institution_id,*orphan_ids))
            for order,broad in enumerate(payload.broad_categories):
                existing=self.get_broad(institution_id,broad.broad_category)
                conn.execute("""INSERT INTO broad_categories VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(institution_id,id) DO UPDATE SET name_ar=excluded.name_ar,name_en=excluded.name_en,definition_ar=excluded.definition_ar,definition_en=excluded.definition_en,is_active=excluded.is_active,sort_order=excluded.sort_order,updated_at=excluded.updated_at""",(institution_id,broad.broad_category,broad.name_ar,broad.name_en,broad.definition_ar,broad.definition_en,int(broad.is_active),order,now))
                if not existing or existing["definition_ar"]!=broad.definition_ar or existing["definition_en"]!=broad.definition_en: conn.execute("DELETE FROM embeddings WHERE institution_id=? AND entity_kind='broad_definition' AND entity_id=?",(institution_id,broad.broad_category))
                for sorder,specific in enumerate(broad.specific_types):
                    existing_s=self.get_specific(institution_id,specific.specific_type)
                    conn.execute("""INSERT INTO specific_types VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(institution_id,id) DO UPDATE SET broad_id=excluded.broad_id,name_ar=excluded.name_ar,name_en=excluded.name_en,definition_ar=excluded.definition_ar,definition_en=excluded.definition_en,is_active=excluded.is_active,sort_order=excluded.sort_order,updated_at=excluded.updated_at""",(institution_id,specific.specific_type,broad.broad_category,specific.name_ar,specific.name_en,specific.definition_ar,specific.definition_en,int(specific.is_active),sorder,now))
                    conn.execute("UPDATE examples SET broad_id=? WHERE institution_id=? AND specific_id=?",(broad.broad_category,institution_id,specific.specific_type))
                    if not existing_s or existing_s["broad_id"]!=broad.broad_category or existing_s["definition_en"]!=specific.definition_en: conn.execute("DELETE FROM embeddings WHERE institution_id=? AND entity_kind='specific_definition' AND entity_id=?",(institution_id,specific.specific_type))
            phs=",".join("?" for _ in new_specific); phb=",".join("?" for _ in new_broad)
            conn.execute(f"DELETE FROM specific_types WHERE institution_id=? AND id NOT IN ({phs})",(institution_id,*new_specific))
            conn.execute(f"DELETE FROM broad_categories WHERE institution_id=? AND id NOT IN ({phb})",(institution_id,*new_broad))
        return impact["will_replace"]

    def examples_replacement_impact(self, institution_id: str, payload: ExamplesPayload) -> dict[str,Any]:
        current={r["id"]:r for r in self.list_examples(institution_id,False)}; incoming={e.id:e for e in payload.examples}
        known={r["id"] for r in self.list_specific(institution_id,False)}
        changed=sum(1 for key,item in incoming.items() if key in current and (current[key]["text"]!=item.text or current[key]["specific_id"]!=item.specific_type))
        return {"current":{"examples":len(current)},"incoming":{"examples":len(incoming)},"will_add":{"examples":len(incoming.keys()-current.keys())},"will_update":{"examples":changed},"will_delete":{"examples":len(current.keys()-incoming.keys())},"unknown_specific_ids":sorted({e.specific_type for e in payload.examples}-known)}

    def replace_examples_selective(self, institution_id: str, payload: ExamplesPayload) -> dict[str,int]:
        self._validate_examples(institution_id,payload.examples); impact=self.examples_replacement_impact(institution_id,payload)
        current={r["id"]:r for r in self.list_examples(institution_id,False)}; incoming={e.id:e for e in payload.examples}
        stale=list(current.keys()-incoming.keys())+[key for key,item in incoming.items() if key in current and (current[key]["text"]!=item.text or current[key]["specific_id"]!=item.specific_type)]
        with self.transaction() as conn:
            if stale:
                ph=",".join("?" for _ in stale); conn.execute(f"DELETE FROM embeddings WHERE institution_id=? AND entity_kind='example' AND entity_id IN ({ph})",(institution_id,*stale))
            conn.execute("DELETE FROM examples WHERE institution_id=?",(institution_id,)); self._insert_examples(conn,institution_id,payload.examples,False)
        return {"examples":len(payload.examples)}

    def taxonomy(self, institution_id: str) -> dict[str, Any]:
        broad_rows = self.list_broad(institution_id, False)
        specific_rows = self.list_specific(institution_id, False)
        grouped: dict[str,list[dict[str,Any]]] = {}
        for row in specific_rows: grouped.setdefault(row["broad_id"],[]).append(row)
        return {"broad_categories":[{"broad_category":b["id"],"name_ar":b["name_ar"],"name_en":b["name_en"],"definition_ar":b["definition_ar"],"definition_en":b["definition_en"],"is_active":bool(b["is_active"]),"specific_types":[{"specific_type":s["id"],"name_ar":s["name_ar"],"name_en":s["name_en"],"definition_ar":s["definition_ar"],"definition_en":s["definition_en"],"is_active":bool(s["is_active"])} for s in grouped.get(b["id"],[])]} for b in broad_rows]}

    def save_embedding(self, institution_id: str, entity_kind: str, entity_id: str, model_key: str, source_hash: str, vector: np.ndarray) -> None:
        arr=np.asarray(vector,dtype=np.float32)
        if arr.ndim != 1 or not np.isfinite(arr).all(): raise ValueError("Embedding must be one finite float32 vector")
        with self.transaction() as conn:
            conn.execute("""INSERT INTO embeddings VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(institution_id,entity_kind,entity_id,model_key) DO UPDATE SET text_hash=excluded.text_hash,dimension=excluded.dimension,vector=excluded.vector,updated_at=excluded.updated_at""",(institution_id,entity_kind,entity_id,model_key,source_hash,int(arr.shape[0]),arr.tobytes(),utc_now()))

    def get_embedding(self, institution_id: str, entity_kind: str, entity_id: str, model_key: str, source_hash: str) -> np.ndarray | None:
        with self._lock:
            row=self._connection.execute("SELECT text_hash,dimension,vector FROM embeddings WHERE institution_id=? AND entity_kind=? AND entity_id=? AND model_key=?",(institution_id,entity_kind,entity_id,model_key)).fetchone()
        if not row or row["text_hash"] != source_hash: return None
        vector=np.frombuffer(row["vector"],dtype=np.float32).copy()
        return vector if vector.shape[0] == int(row["dimension"]) else None

    def statistics(self, institution_id: str) -> dict[str, int]:
        with self._lock:
            return {table:int(self._connection.execute(f"SELECT COUNT(*) FROM {table} WHERE institution_id=?",(institution_id,)).fetchone()[0]) for table in self.TABLES}

    def last_updated(self, institution_id: str) -> str | None:
        with self._lock:
            row=self._connection.execute("SELECT MAX(updated_at) FROM (SELECT updated_at FROM broad_categories WHERE institution_id=? UNION ALL SELECT updated_at FROM specific_types WHERE institution_id=? UNION ALL SELECT updated_at FROM examples WHERE institution_id=? UNION ALL SELECT updated_at FROM embeddings WHERE institution_id=?)",(institution_id,)*4).fetchone()
        return row[0] if row else None
