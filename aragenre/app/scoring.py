from __future__ import annotations

import re

import numpy as np


AR_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
AR_LETTERS = re.compile(r"[^\u0600-\u06FF0-9A-Za-z]+")


def normalize_arabic(text: str) -> str:
    value = AR_DIACRITICS.sub("", str(text))
    value = (
        value.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ى", "ي")
        .replace("ؤ", "و")
        .replace("ئ", "ي")
        .replace("ة", "ه")
    )
    value = AR_LETTERS.sub(" ", value.lower())
    return re.sub(r"\s+", " ", value).strip()


def tokenize(text: str) -> list[str]:
    return [word for word in normalize_arabic(text).split() if len(word) > 1]


def row_zscore(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr[None, :]
    mean = arr.mean(axis=1, keepdims=True)
    std = arr.std(axis=1, keepdims=True)
    return (arr - mean) / np.maximum(std, 1e-6)


def bm25_relative_similarity(raw: np.ndarray) -> np.ndarray:
    arr = np.maximum(np.asarray(raw, dtype=np.float32), 0.0)
    if arr.ndim == 1:
        arr = arr[None, :]
    maximum = arr.max(axis=1, keepdims=True)
    return np.divide(
        arr,
        np.maximum(maximum, 1e-8),
        out=np.zeros_like(arr),
        where=maximum > 0,
    )


def softmax_weighted_top(values: np.ndarray, temperature: float) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float32)
    shifted = arr / max(float(temperature), 1e-6)
    shifted = shifted - shifted.max(axis=1, keepdims=True)
    weights = np.exp(shifted)
    weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-8)
    return np.sum(weights * arr, axis=1)


def balanced_per_class_scores(
    score_matrix: np.ndarray,
    labels: np.ndarray,
    n_labels: int,
    top_m: int,
    temperature: float,
) -> tuple[np.ndarray, list[list[int]]]:
    scores = np.asarray(score_matrix, dtype=np.float32)
    if scores.ndim == 1:
        scores = scores[None, :]
    labels = np.asarray(labels, dtype=np.int64)

    class_scores = np.full((scores.shape[0], n_labels), -1e9, dtype=np.float32)
    selected_neighbors: list[list[int]] = [[] for _ in range(n_labels)]

    for label in range(n_labels):
        allowed = np.where(labels == label)[0]
        if len(allowed) == 0:
            continue
        effective_m = min(int(top_m), len(allowed))
        local = scores[:, allowed]
        local_top = np.argpartition(-local, kth=effective_m - 1, axis=1)[:, :effective_m]
        local_values = np.take_along_axis(local, local_top, axis=1)
        order = np.argsort(-local_values, axis=1, kind="stable")
        local_top = np.take_along_axis(local_top, order, axis=1)
        local_values = np.take_along_axis(local_values, order, axis=1)
        class_scores[:, label] = softmax_weighted_top(local_values, temperature)
        selected_neighbors[label] = allowed[local_top[0]].astype(int).tolist()

    return class_scores, selected_neighbors


def top_m_mean_per_label(
    score_matrix: np.ndarray,
    example_label_idx: np.ndarray,
    n_labels: int,
    top_m: int,
) -> np.ndarray:
    scores = np.asarray(score_matrix, dtype=np.float32)
    if scores.ndim == 1:
        scores = scores[None, :]
    labels = np.asarray(example_label_idx, dtype=np.int64)
    result = np.full((scores.shape[0], n_labels), -1e9, dtype=np.float32)

    for label in range(n_labels):
        allowed = np.where(labels == label)[0]
        if len(allowed) == 0:
            continue
        effective_m = min(int(top_m), len(allowed))
        local = scores[:, allowed]
        idx = np.argpartition(-local, kth=effective_m - 1, axis=1)[:, :effective_m]
        values = np.take_along_axis(local, idx, axis=1)
        result[:, label] = values.mean(axis=1)
    return result


def ranks_from_scores(scores: np.ndarray) -> np.ndarray:
    arr = np.asarray(scores, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr[None, :]
    order = np.argsort(-arr, axis=1, kind="stable")
    ranks = np.empty_like(order, dtype=np.int16)
    rows = np.arange(arr.shape[0])[:, None]
    ranks[rows, order] = np.arange(1, arr.shape[1] + 1, dtype=np.int16)[None, :]
    return ranks


def truncate_ranks(full_ranks: np.ndarray, k: int) -> np.ndarray:
    ranks = np.asarray(full_ranks)
    effective_k = min(int(k), ranks.shape[1])
    return np.where(ranks <= effective_k, ranks, 0).astype(np.int16)


def weighted_rrf(
    rank_matrices: list[np.ndarray],
    weights: tuple[float, ...],
    constant: int,
) -> np.ndarray:
    if len(rank_matrices) != len(weights):
        raise ValueError("Rank matrices and weights must have the same length")
    n_rows, n_labels = rank_matrices[0].shape
    fused = np.zeros((n_rows, n_labels), dtype=np.float32)
    for ranks, weight in zip(rank_matrices, weights):
        ranks = np.asarray(ranks)
        present = ranks > 0
        contribution = np.zeros((n_rows, n_labels), dtype=np.float32)
        contribution[present] = float(weight) / (
            float(constant) + ranks[present].astype(np.float32)
        )
        fused += contribution
    return fused


def deterministic_argmax(
    fused: np.ndarray,
    arabic_full_ranks: np.ndarray,
    e5_full_ranks: np.ndarray,
    bm25_full_ranks: np.ndarray,
) -> np.ndarray:
    fused = np.asarray(fused)
    prediction = np.empty(fused.shape[0], dtype=np.int64)
    for row_idx in range(fused.shape[0]):
        best = np.flatnonzero(
            np.isclose(fused[row_idx], fused[row_idx].max(), rtol=0, atol=1e-12)
        )
        if len(best) == 1:
            prediction[row_idx] = int(best[0])
            continue
        order = np.lexsort(
            (
                bm25_full_ranks[row_idx, best],
                e5_full_ranks[row_idx, best],
                arabic_full_ranks[row_idx, best],
            )
        )
        prediction[row_idx] = int(best[order[0]])
    return prediction
