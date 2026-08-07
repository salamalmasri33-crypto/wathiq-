from __future__ import annotations

import hashlib
import threading
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
from .bm25 import BM25Okapi

from .database import SQLiteStore
from .embeddings import EmbeddingModels
from .scoring import (
    balanced_per_class_scores,
    bm25_relative_similarity,
    deterministic_argmax,
    ranks_from_scores,
    row_zscore,
    tokenize,
    top_m_mean_per_label,
    truncate_ranks,
    weighted_rrf,
)
from .settings import Settings


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class RuntimeIndex:
    broad_rows: list[dict[str, Any]]
    specific_rows: list[dict[str, Any]]
    example_rows: list[dict[str, Any]]

    broad_ids: list[str]
    specific_ids: list[str]
    broad_id_to_idx: dict[str, int]
    specific_id_to_idx: dict[str, int]
    specific_to_broad: dict[str, str]

    broad_defs_e5: np.ndarray
    broad_defs_ar: np.ndarray
    specific_defs_e5: np.ndarray
    examples_e5: np.ndarray
    examples_ar: np.ndarray
    example_broad_idx: np.ndarray
    example_specific_idx: np.ndarray
    bm25: BM25Okapi


class WathiqClassifier:
    def __init__(
        self,
        store: SQLiteStore,
        models: EmbeddingModels,
        settings: Settings,
        institution_id: str,
    ):
        self.store = store
        self.models = models
        self.settings = settings
        self.institution_id = institution_id
        self._index: RuntimeIndex | None = None
        self._warnings: list[str] = []
        self._last_error: str | None = None
        self._lock = threading.RLock()

    @property
    def ready(self) -> bool:
        return self._index is not None

    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def invalidate(self) -> None:
        with self._lock:
            self._index = None

    def _cached_or_encode(
        self,
        *,
        entity_kind: str,
        model_key: str,
        entity_ids: list[str],
        texts: list[str],
        encoder: Callable[[list[str]], np.ndarray],
    ) -> np.ndarray:
        if len(entity_ids) != len(texts):
            raise ValueError("Embedding ids and texts length mismatch")
        vectors: list[np.ndarray | None] = [None] * len(texts)
        missing_indices: list[int] = []

        for idx, (entity_id, text) in enumerate(zip(entity_ids, texts)):
            source_hash = content_hash(text)
            cached = self.store.get_embedding(
                self.institution_id, entity_kind, entity_id, model_key, source_hash
            )
            if cached is None:
                missing_indices.append(idx)
            else:
                vectors[idx] = cached

        if missing_indices:
            encoded = encoder([texts[idx] for idx in missing_indices])
            for local_idx, global_idx in enumerate(missing_indices):
                vector = encoded[local_idx].astype(np.float32)
                vectors[global_idx] = vector
                self.store.save_embedding(
                    self.institution_id,
                    entity_kind,
                    entity_ids[global_idx],
                    model_key,
                    content_hash(texts[global_idx]),
                    vector,
                )

        if not vectors or any(vector is None for vector in vectors):
            raise RuntimeError(f"Failed to prepare embeddings for {entity_kind}/{model_key}")
        return np.stack([np.asarray(vector, dtype=np.float32) for vector in vectors])

    def sync_definition_embeddings(self) -> dict[str, int]:
        broad_rows = self.store.list_broad(self.institution_id, active_only=True)
        specific_rows = self.store.list_specific(self.institution_id, active_only=True)
        if not broad_rows:
            return {"broad_definitions": 0, "specific_definitions": 0}

        broad_ids = [row["id"] for row in broad_rows]
        self._cached_or_encode(
            entity_kind="broad_definition",
            model_key=f"e5::{self.settings.e5_model}",
            entity_ids=broad_ids,
            texts=[row["definition_en"] for row in broad_rows],
            encoder=lambda texts: self.models.encode_e5(texts, "passage"),
        )
        self._cached_or_encode(
            entity_kind="broad_definition",
            model_key=f"arabic::{self.settings.arabic_model}",
            entity_ids=broad_ids,
            texts=[row["definition_ar"] for row in broad_rows],
            encoder=self.models.encode_arabic,
        )

        broad_by_id = {row["id"]: row for row in broad_rows}
        specific_ids = [row["id"] for row in specific_rows]
        specific_definition_texts = [
            (
                f"Specific genre: {row['name_en']} ({row['id']}). "
                f"Broad genre: {broad_by_id[row['broad_id']]['name_en']} "
                f"({row['broad_id']}). Definition: {row['definition_en']}"
            )
            for row in specific_rows
        ]
        if specific_rows:
            self._cached_or_encode(
                entity_kind="specific_definition",
                model_key=f"e5::{self.settings.e5_model}",
                entity_ids=specific_ids,
                texts=specific_definition_texts,
                encoder=lambda texts: self.models.encode_e5(texts, "passage"),
            )
        return {
            "broad_definitions": len(broad_rows),
            "specific_definitions": len(specific_rows),
        }

    def sync_example_embeddings(self, example_ids: list[str] | None = None) -> dict[str, int]:
        rows = self.store.list_examples(self.institution_id, active_only=False)
        if example_ids is not None:
            wanted = set(example_ids)
            rows = [row for row in rows if row["id"] in wanted]
        if not rows:
            return {"examples": 0}
        ids = [row["id"] for row in rows]
        texts = [row["text"] for row in rows]
        self._cached_or_encode(
            entity_kind="example", model_key=f"e5::{self.settings.e5_model}",
            entity_ids=ids, texts=texts,
            encoder=lambda values: self.models.encode_e5(values, "passage"),
        )
        self._cached_or_encode(
            entity_kind="example", model_key=f"arabic::{self.settings.arabic_model}",
            entity_ids=ids, texts=texts, encoder=self.models.encode_arabic,
        )
        return {"examples": len(rows)}

    def rebuild_index(self) -> dict[str, Any]:
        with self._lock:
            try:
                broad_rows = self.store.list_broad(self.institution_id, active_only=True)
                specific_rows = self.store.list_specific(self.institution_id, active_only=True)
                example_rows = self.store.list_examples(self.institution_id, active_only=True)

                if not broad_rows:
                    raise ValueError("No active broad categories are configured")
                if not specific_rows:
                    raise ValueError("No active specific types are configured")
                if not example_rows:
                    raise ValueError("No active examples are configured")

                broad_ids = [row["id"] for row in broad_rows]
                specific_ids = [row["id"] for row in specific_rows]
                broad_id_to_idx = {value: idx for idx, value in enumerate(broad_ids)}
                specific_id_to_idx = {value: idx for idx, value in enumerate(specific_ids)}
                specific_to_broad = {row["id"]: row["broad_id"] for row in specific_rows}

                active_broad = set(broad_ids)
                for row in specific_rows:
                    if row["broad_id"] not in active_broad:
                        raise ValueError(
                            f"Specific type {row['id']} belongs to an inactive broad category"
                        )

                # Definitions.
                broad_defs_e5 = self._cached_or_encode(
                    entity_kind="broad_definition",
                    model_key=f"e5::{self.settings.e5_model}",
                    entity_ids=broad_ids,
                    texts=[row["definition_en"] for row in broad_rows],
                    encoder=lambda texts: self.models.encode_e5(texts, "passage"),
                )
                broad_defs_ar = self._cached_or_encode(
                    entity_kind="broad_definition",
                    model_key=f"arabic::{self.settings.arabic_model}",
                    entity_ids=broad_ids,
                    texts=[row["definition_ar"] for row in broad_rows],
                    encoder=self.models.encode_arabic,
                )

                broad_by_id = {row["id"]: row for row in broad_rows}
                specific_definition_texts = [
                    (
                        f"Specific genre: {row['name_en']} ({row['id']}). "
                        f"Broad genre: {broad_by_id[row['broad_id']]['name_en']} "
                        f"({row['broad_id']}). Definition: {row['definition_en']}"
                    )
                    for row in specific_rows
                ]
                specific_defs_e5 = self._cached_or_encode(
                    entity_kind="specific_definition",
                    model_key=f"e5::{self.settings.e5_model}",
                    entity_ids=specific_ids,
                    texts=specific_definition_texts,
                    encoder=lambda texts: self.models.encode_e5(texts, "passage"),
                )

                # Examples are used by both the Broad and Specific stages.
                example_ids = [row["id"] for row in example_rows]
                example_texts = [row["text"] for row in example_rows]
                examples_e5 = self._cached_or_encode(
                    entity_kind="example",
                    model_key=f"e5::{self.settings.e5_model}",
                    entity_ids=example_ids,
                    texts=example_texts,
                    encoder=lambda texts: self.models.encode_e5(texts, "passage"),
                )
                examples_ar = self._cached_or_encode(
                    entity_kind="example",
                    model_key=f"arabic::{self.settings.arabic_model}",
                    entity_ids=example_ids,
                    texts=example_texts,
                    encoder=self.models.encode_arabic,
                )

                example_broad_idx = np.array(
                    [broad_id_to_idx[row["broad_id"]] for row in example_rows],
                    dtype=np.int64,
                )
                example_specific_idx = np.array(
                    [specific_id_to_idx[row["specific_id"]] for row in example_rows],
                    dtype=np.int64,
                )
                bm25 = BM25Okapi([tokenize(text) for text in example_texts])

                warnings: list[str] = []
                broad_counts = Counter(row["broad_id"] for row in example_rows)
                specific_counts = Counter(row["specific_id"] for row in example_rows)
                for broad_id in broad_ids:
                    count = broad_counts[broad_id]
                    if count < self.settings.broad_top_m:
                        warnings.append(
                            f"Broad {broad_id} has {count} examples; "
                            f"the original pipeline uses at least {self.settings.broad_top_m}."
                        )
                for specific_id in specific_ids:
                    count = specific_counts[specific_id]
                    if count < self.settings.specific_examples_per_label:
                        warnings.append(
                            f"Specific {specific_id} has {count} examples; "
                            f"the original pipeline uses at least "
                            f"{self.settings.specific_examples_per_label}."
                        )

                self._index = RuntimeIndex(
                    broad_rows=broad_rows,
                    specific_rows=specific_rows,
                    example_rows=example_rows,
                    broad_ids=broad_ids,
                    specific_ids=specific_ids,
                    broad_id_to_idx=broad_id_to_idx,
                    specific_id_to_idx=specific_id_to_idx,
                    specific_to_broad=specific_to_broad,
                    broad_defs_e5=broad_defs_e5,
                    broad_defs_ar=broad_defs_ar,
                    specific_defs_e5=specific_defs_e5,
                    examples_e5=examples_e5,
                    examples_ar=examples_ar,
                    example_broad_idx=example_broad_idx,
                    example_specific_idx=example_specific_idx,
                    bm25=bm25,
                )
                self._warnings = warnings
                self._last_error = None
                return self.statistics()
            except Exception as exc:
                self._index = None
                self._last_error = str(exc)
                raise

    def statistics(self) -> dict[str, Any]:
        base = self.store.statistics(self.institution_id)
        if self._index is None:
            return {
                **base,
                "index_ready": False,
                "last_error": self._last_error,
            }
        broad_counts = Counter(row["broad_id"] for row in self._index.example_rows)
        specific_counts = Counter(row["specific_id"] for row in self._index.example_rows)
        return {
            **base,
            "index_ready": True,
            "device": self.models.device,
            "examples_per_broad": dict(broad_counts),
            "examples_per_specific": dict(specific_counts),
            "warnings": list(self._warnings),
        }

    def classify(self, text: str, debug: bool = False) -> dict[str, Any]:
        with self._lock:
            index = self._index
            if index is None:
                raise RuntimeError(
                    "Classifier index is not ready. Import definitions and examples, "
                    "then call /config/rebuild-index."
                )

            document = " ".join(text.split())[: self.settings.max_input_chars]
            query_e5 = self.models.encode_e5([document], "query")
            query_ar = self.models.encode_arabic([document])
            bm25_raw = np.asarray(index.bm25.get_scores(tokenize(document)), dtype=np.float32)[
                None, :
            ]

            # -----------------------------------------------------------------
            # Stage 1: exact V10 core for Broad classification.
            # -----------------------------------------------------------------
            broad_e5_sim = np.clip(query_e5 @ index.examples_e5.T, -1.0, 1.0)
            broad_ar_sim = np.clip(query_ar @ index.examples_ar.T, -1.0, 1.0)
            broad_bm_sim = bm25_relative_similarity(bm25_raw)

            broad_hybrid = (
                self.settings.semantic_e5_weight * row_zscore(broad_e5_sim)
                + self.settings.semantic_arabic_weight * row_zscore(broad_ar_sim)
                + self.settings.bm25_weight * row_zscore(broad_bm_sim)
            ).astype(np.float32)

            broad_class_scores, neighbors = balanced_per_class_scores(
                broad_hybrid,
                index.example_broad_idx,
                len(index.broad_ids),
                self.settings.broad_top_m,
                self.settings.softmax_temperature,
            )

            broad_def_e5_raw = np.clip(query_e5 @ index.broad_defs_e5.T, -1.0, 1.0)
            broad_def_ar_raw = np.clip(query_ar @ index.broad_defs_ar.T, -1.0, 1.0)
            broad_definition_score = (
                self.settings.broad_definition_e5_weight
                * row_zscore(broad_def_e5_raw)
                + self.settings.broad_definition_arabic_weight
                * row_zscore(broad_def_ar_raw)
            ).astype(np.float32)

            broad_final = (
                self.settings.broad_example_weight * row_zscore(broad_class_scores)
                + self.settings.broad_definition_weight
                * row_zscore(broad_definition_score)
            ).astype(np.float32)
            broad_idx = int(np.argmax(broad_final[0]))
            broad_id = index.broad_ids[broad_idx]

            # -----------------------------------------------------------------
            # Stage 2: V18 independent Weighted RRF K=20 inside selected Broad.
            # -----------------------------------------------------------------
            candidate_global_cols = np.array(
                [
                    idx
                    for idx, specific_id in enumerate(index.specific_ids)
                    if index.specific_to_broad[specific_id] == broad_id
                ],
                dtype=np.int64,
            )
            if len(candidate_global_cols) == 0:
                raise RuntimeError(f"Broad {broad_id} has no active specific types")

            global_to_local = {
                int(global_idx): local_idx
                for local_idx, global_idx in enumerate(candidate_global_cols)
            }
            example_cols = np.where(index.example_broad_idx == broad_idx)[0]
            if len(example_cols) == 0:
                raise RuntimeError(f"Broad {broad_id} has no examples")

            local_example_labels = np.array(
                [
                    global_to_local[int(index.example_specific_idx[example_idx])]
                    for example_idx in example_cols
                ],
                dtype=np.int64,
            )

            e5_scores = np.clip(
                query_e5 @ index.specific_defs_e5[candidate_global_cols].T,
                -1.0,
                1.0,
            )
            ar_example_scores = np.clip(
                query_ar @ index.examples_ar[example_cols].T,
                -1.0,
                1.0,
            )
            bm_example_scores = bm25_raw[:, example_cols]

            ar_label_scores = top_m_mean_per_label(
                ar_example_scores,
                local_example_labels,
                len(candidate_global_cols),
                self.settings.specific_examples_per_label,
            )
            bm_label_scores = top_m_mean_per_label(
                bm_example_scores,
                local_example_labels,
                len(candidate_global_cols),
                self.settings.specific_examples_per_label,
            )

            e5_full_ranks = ranks_from_scores(e5_scores)
            ar_full_ranks = ranks_from_scores(ar_label_scores)
            bm_full_ranks = ranks_from_scores(bm_label_scores)

            fused = weighted_rrf(
                [
                    truncate_ranks(e5_full_ranks, self.settings.specific_k),
                    truncate_ranks(ar_full_ranks, self.settings.specific_k),
                    truncate_ranks(bm_full_ranks, self.settings.specific_k),
                ],
                (
                    self.settings.rrf_e5_weight,
                    self.settings.rrf_arabic_weight,
                    self.settings.rrf_bm25_weight,
                ),
                self.settings.rrf_constant,
            )
            local_specific_idx = int(
                deterministic_argmax(
                    fused, ar_full_ranks, e5_full_ranks, bm_full_ranks
                )[0]
            )
            global_specific_idx = int(candidate_global_cols[local_specific_idx])
            specific_id = index.specific_ids[global_specific_idx]

            broad_row = index.broad_rows[broad_idx]
            specific_row = index.specific_rows[global_specific_idx]
            response: dict[str, Any] = {
                "broad_category": broad_id,
                "broad_category_ar": broad_row["name_ar"],
                "specific_type": specific_id,
                "specific_type_ar": specific_row["name_ar"],
                "model_pipeline": "V10 Broad + V18 Specific K20",
            }

            if debug:
                broad_order = np.argsort(-broad_final[0], kind="stable")
                specific_order = np.argsort(-fused[0], kind="stable")
                response["debug"] = {
                    "broad_candidates": [
                        {
                            "id": index.broad_ids[int(candidate)],
                            "name_ar": index.broad_rows[int(candidate)]["name_ar"],
                            "final_score": float(broad_final[0, candidate]),
                            "example_score": float(broad_class_scores[0, candidate]),
                            "definition_score": float(
                                broad_definition_score[0, candidate]
                            ),
                            "nearest_example_ids": [
                                index.example_rows[example_idx]["id"]
                                for example_idx in neighbors[int(candidate)]
                            ],
                        }
                        for candidate in broad_order
                    ],
                    "specific_candidates": [
                        {
                            "id": index.specific_ids[
                                int(candidate_global_cols[int(local_candidate)])
                            ],
                            "name_ar": index.specific_rows[
                                int(candidate_global_cols[int(local_candidate)])
                            ]["name_ar"],
                            "rrf_score": float(fused[0, local_candidate]),
                            "e5_rank": int(e5_full_ranks[0, local_candidate]),
                            "arabic_rank": int(ar_full_ranks[0, local_candidate]),
                            "bm25_rank": int(bm_full_ranks[0, local_candidate]),
                        }
                        for local_candidate in specific_order
                    ],
                    "text_chars_used": len(document),
                }
            return response
