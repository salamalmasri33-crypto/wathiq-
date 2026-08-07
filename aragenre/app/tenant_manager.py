from __future__ import annotations

import threading

from .classifier import WathiqClassifier
from .database import SQLiteStore
from .embeddings import EmbeddingModels
from .settings import Settings


class InstitutionClassifierManager:
    """Lazily owns one classifier and lock per institution."""

    def __init__(self, store: SQLiteStore, models: EmbeddingModels, settings: Settings):
        self.store = store
        self.models = models
        self.settings = settings
        self._classifiers: dict[str, WathiqClassifier] = {}
        self._locks: dict[str, threading.RLock] = {}
        self._manager_lock = threading.RLock()

    @property
    def loaded_indexes(self) -> int:
        with self._manager_lock:
            return sum(classifier.ready for classifier in self._classifiers.values())

    def _lock_for(self, institution_id: str) -> threading.RLock:
        with self._manager_lock:
            return self._locks.setdefault(institution_id, threading.RLock())

    def get(self, institution_id: str) -> WathiqClassifier:
        with self._manager_lock:
            return self._classifiers.setdefault(
                institution_id,
                WathiqClassifier(self.store, self.models, self.settings, institution_id),
            )

    def invalidate(self, institution_id: str) -> None:
        with self._lock_for(institution_id):
            classifier = self.get(institution_id)
            classifier.invalidate()

    def rebuild(self, institution_id: str) -> dict:
        with self._lock_for(institution_id):
            return self.get(institution_id).rebuild_index()

    def sync_definitions(self, institution_id: str) -> dict:
        with self._lock_for(institution_id):
            return self.get(institution_id).sync_definition_embeddings()

    def sync_examples(self, institution_id: str, example_ids: list[str] | None = None) -> dict:
        with self._lock_for(institution_id):
            return self.get(institution_id).sync_example_embeddings(example_ids)

    def ensure_loaded(self, institution_id: str) -> WathiqClassifier:
        with self._lock_for(institution_id):
            classifier = self.get(institution_id)
            if not classifier.ready:
                classifier.rebuild_index()
            return classifier
