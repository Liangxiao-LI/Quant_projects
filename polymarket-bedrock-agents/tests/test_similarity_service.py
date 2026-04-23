"""Similarity helpers."""

import pytest

from app.services.similarity_service import cosine_similarity, pearson_correlation


def test_cosine_similarity_basic() -> None:
    a = [1.0, 0.0]
    b = [1.0, 0.0]
    assert cosine_similarity(a, b) == pytest.approx(1.0)


def test_pearson_correlation_perfect() -> None:
    x = [1.0, 2.0, 3.0, 4.0]
    y = [2.0, 4.0, 6.0, 8.0]
    r = pearson_correlation(x, y)
    assert r is not None
    assert r == pytest.approx(1.0)
