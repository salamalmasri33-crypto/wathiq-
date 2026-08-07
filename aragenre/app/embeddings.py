from __future__ import annotations

import threading
from typing import Literal

import numpy as np

from .settings import Settings


class EmbeddingModels:
    """Lazy, thread-safe access to the two frozen embedding models."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._e5 = None
        self._arabic = None
        self._device: str | None = None
        self._lock = threading.RLock()

    @property
    def device(self) -> str:
        if self._device is None:
            self._resolve_device()
        return self._device or "cpu"

    def _resolve_device(self) -> None:
        import torch

        requested = self.settings.device.lower()
        if requested == "auto":
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        elif requested in {"cpu", "cuda"}:
            if requested == "cuda" and not torch.cuda.is_available():
                raise RuntimeError("MODEL_DEVICE=cuda but CUDA is unavailable")
            self._device = requested
        else:
            raise ValueError("MODEL_DEVICE must be auto, cpu, or cuda")

    def _load_e5(self):
        with self._lock:
            if self._e5 is None:
                from sentence_transformers import SentenceTransformer

                self._e5 = SentenceTransformer(self.settings.e5_model, device=self.device)
                self._e5.max_seq_length = self.settings.e5_max_length
                for parameter in self._e5.parameters():
                    parameter.requires_grad = False
            return self._e5

    def _load_arabic(self):
        with self._lock:
            if self._arabic is None:
                from sentence_transformers import SentenceTransformer

                self._arabic = SentenceTransformer(
                    self.settings.arabic_model, device=self.device
                )
                self._arabic.max_seq_length = self.settings.arabic_max_length
                for parameter in self._arabic.parameters():
                    parameter.requires_grad = False
            return self._arabic

    def encode_e5(
        self,
        texts: list[str],
        role: Literal["query", "passage"],
    ) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        model = self._load_e5()
        prefixed = [f"{role}: {text.strip()}" for text in texts]
        with self._lock:
            return model.encode(
                prefixed,
                batch_size=self.settings.e5_batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).astype(np.float32)

    def encode_arabic(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        model = self._load_arabic()
        with self._lock:
            return model.encode(
                [text.strip() for text in texts],
                batch_size=self.settings.arabic_batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).astype(np.float32)

    def status(self) -> dict[str, object]:
        return {
            "device": self.device,
            "e5_model": self.settings.e5_model,
            "arabic_model": self.settings.arabic_model,
            "e5_loaded": self._e5 is not None,
            "arabic_loaded": self._arabic is not None,
        }
