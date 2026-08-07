from __future__ import annotations

import math
from collections import Counter

import numpy as np


class BM25Okapi:
    """Small compatible implementation of the BM25Okapi formula used by rank_bm25.

    It is vendored so the service has one fewer runtime dependency. Defaults match
    rank-bm25 0.2.2: k1=1.5, b=0.75, epsilon=0.25.
    """

    def __init__(
        self,
        corpus: list[list[str]],
        k1: float = 1.5,
        b: float = 0.75,
        epsilon: float = 0.25,
    ):
        if not corpus:
            raise ValueError("BM25 corpus cannot be empty")
        self.k1 = float(k1)
        self.b = float(b)
        self.epsilon = float(epsilon)
        self.corpus_size = len(corpus)
        self.doc_freqs = [Counter(document) for document in corpus]
        self.doc_len = np.asarray([len(document) for document in corpus], dtype=np.float32)
        self.avgdl = float(self.doc_len.mean()) if self.corpus_size else 0.0
        self.idf = self._calculate_idf()

    def _calculate_idf(self) -> dict[str, float]:
        document_frequency: Counter[str] = Counter()
        for frequencies in self.doc_freqs:
            document_frequency.update(frequencies.keys())

        idf: dict[str, float] = {}
        negative_words: list[str] = []
        idf_sum = 0.0
        for word, frequency in document_frequency.items():
            value = math.log(self.corpus_size - frequency + 0.5) - math.log(
                frequency + 0.5
            )
            idf[word] = value
            idf_sum += value
            if value < 0:
                negative_words.append(word)

        average_idf = idf_sum / max(len(idf), 1)
        floor = self.epsilon * average_idf
        for word in negative_words:
            idf[word] = floor
        return idf

    def get_scores(self, query_tokens: list[str]) -> np.ndarray:
        score = np.zeros(self.corpus_size, dtype=np.float32)
        if not query_tokens:
            return score

        denominator_length = self.k1 * (
            1.0 - self.b + self.b * self.doc_len / max(self.avgdl, 1e-8)
        )
        for token in query_tokens:
            token_frequency = np.asarray(
                [frequencies.get(token, 0) for frequencies in self.doc_freqs],
                dtype=np.float32,
            )
            numerator = token_frequency * (self.k1 + 1.0)
            denominator = token_frequency + denominator_length
            score += float(self.idf.get(token, 0.0)) * np.divide(
                numerator,
                np.maximum(denominator, 1e-8),
                out=np.zeros_like(numerator),
                where=denominator > 0,
            )
        return score
