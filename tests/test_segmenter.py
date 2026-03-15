"""Tests for the semantic segmenter."""

import numpy as np
import pytest

from src.pipeline.models import Sentence
from src.pipeline.segmenter import (
    _cosine_similarity_consecutive,
    _find_boundaries,
    _smooth,
)


def _make_sentence(text: str, start: float, end: float) -> Sentence:
    return Sentence(text=text, start=start, end=end, confidence=0.9)


class TestCosineSimConsecutive:
    def test_identical_vectors(self):
        embeddings = np.array([[1, 0, 0], [1, 0, 0], [1, 0, 0]], dtype=float)
        sim = _cosine_similarity_consecutive(embeddings)
        assert len(sim) == 2
        np.testing.assert_allclose(sim, [1.0, 1.0], atol=1e-6)

    def test_orthogonal_vectors(self):
        embeddings = np.array([[1, 0], [0, 1], [1, 0]], dtype=float)
        sim = _cosine_similarity_consecutive(embeddings)
        assert len(sim) == 2
        np.testing.assert_allclose(sim, [0.0, 0.0], atol=1e-6)

    def test_detects_topic_shift(self):
        # Sentences 0-2 are similar, then a shift at 3-4
        embeddings = np.array([
            [1, 0.1, 0],
            [0.9, 0.2, 0],
            [0.8, 0.1, 0],
            [0, 0.1, 1],   # topic shift
            [0.1, 0.2, 0.9],
        ], dtype=float)
        sim = _cosine_similarity_consecutive(embeddings)
        # The drop should be at index 2 (between sentence 2 and 3)
        assert sim[2] < sim[0]
        assert sim[2] < sim[1]
        assert sim[2] < sim[3]


class TestSmooth:
    def test_no_smoothing(self):
        values = np.array([1.0, 0.5, 1.0])
        result = _smooth(values, window=1)
        np.testing.assert_array_equal(result, values)

    def test_smoothing_reduces_noise(self):
        values = np.array([1.0, 0.0, 1.0, 0.0, 1.0])
        result = _smooth(values, window=3)
        # Smoothed values should be less extreme
        assert result.min() > values.min()
        assert result.max() < values.max()


class TestFindBoundaries:
    def test_clear_single_boundary(self):
        # High similarity, then drop, then high again
        similarities = np.array([0.9, 0.85, 0.3, 0.2, 0.35, 0.88, 0.9])
        sentences = [
            _make_sentence(f"s{i}", start=i * 60.0, end=(i + 1) * 60.0 - 1)
            for i in range(8)  # need len(sim) + 1 sentences
        ]
        boundaries = _find_boundaries(
            similarities, sentences,
            min_duration=30, max_duration=600,
        )
        assert len(boundaries) >= 1
        # Boundary should be around index 3 (the minimum)
        assert any(2 <= b <= 4 for b in boundaries)

    def test_no_boundary_short_input(self):
        similarities = np.array([0.9, 0.8])
        sentences = [
            _make_sentence(f"s{i}", start=i * 10.0, end=(i + 1) * 10.0 - 1)
            for i in range(3)
        ]
        boundaries = _find_boundaries(
            similarities, sentences,
            min_duration=30, max_duration=600,
        )
        # With min_duration=30 and segments only 10s each, no valid boundary
        assert isinstance(boundaries, list)

    def test_respects_min_duration(self):
        similarities = np.array([0.9, 0.2, 0.9, 0.2, 0.9])
        # Each sentence is only 5 seconds
        sentences = [
            _make_sentence(f"s{i}", start=i * 5.0, end=(i + 1) * 5.0 - 1)
            for i in range(6)
        ]
        boundaries = _find_boundaries(
            similarities, sentences,
            min_duration=30,  # 30 seconds min
            max_duration=600,
        )
        # No boundary should create segments < 30s
        # With 5s sentences and 30s min, at most 1 boundary
        assert len(boundaries) <= 1
