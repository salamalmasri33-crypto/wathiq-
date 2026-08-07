import numpy as np

from app.scoring import (
    balanced_per_class_scores,
    deterministic_argmax,
    ranks_from_scores,
    top_m_mean_per_label,
    truncate_ranks,
    weighted_rrf,
)


def test_balanced_scores_are_class_balanced():
    scores = np.array([[0.9, 0.8, 0.1, 0.7, 0.6, 0.2]], dtype=np.float32)
    labels = np.array([0, 0, 0, 1, 1, 1])
    result, _ = balanced_per_class_scores(scores, labels, 2, 2, 0.5)
    assert result.shape == (1, 2)
    assert result[0, 0] > result[0, 1]


def test_weighted_rrf_prefers_consensus():
    e5 = np.array([[1, 2]])
    arabic = np.array([[2, 1]])
    bm25 = np.array([[2, 1]])
    fused = weighted_rrf([e5, arabic, bm25], (0.3, 0.5, 0.2), 10)
    pred = deterministic_argmax(fused, arabic, e5, bm25)
    assert int(pred[0]) == 1


def test_top_m_mean_per_label():
    scores = np.array([[0.9, 0.7, 0.2, 0.8, 0.6, 0.1]], dtype=np.float32)
    labels = np.array([0, 0, 0, 1, 1, 1])
    result = top_m_mean_per_label(scores, labels, 2, 2)
    assert np.allclose(result, [[0.8, 0.7]])


def test_rank_truncation():
    ranks = ranks_from_scores(np.array([[0.2, 0.9, 0.4]], dtype=np.float32))
    assert ranks.tolist() == [[3, 1, 2]]
    assert truncate_ranks(ranks, 2).tolist() == [[0, 1, 2]]
