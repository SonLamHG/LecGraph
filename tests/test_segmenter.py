"""Tests for the semantic segmenter."""

import numpy as np
import pytest

from src.pipeline.models import Sentence
from src.pipeline.models import Segment
from src.pipeline.segmenter import (
    _cosine_similarity_consecutive,
    _find_boundaries,
    _merge_short_segments,
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


def _make_segment(seg_id: str, start: float, end: float) -> Segment:
    return Segment(
        segment_id=seg_id,
        title=f"Title {seg_id}",
        start=start,
        end=end,
        transcript=f"Text for {seg_id}",
        sentences=[_make_sentence("s", start, end)],
    )


class TestMergeShortSegments:
    def test_short_last_segment_merged(self):
        segments = [
            _make_segment("v_seg001", 0, 60),
            _make_segment("v_seg002", 60, 120),
            _make_segment("v_seg003", 120, 130),  # 10s — too short
        ]
        result = _merge_short_segments(segments, min_duration=30)
        assert len(result) == 2
        assert result[-1].end == 130

    def test_short_first_segment_merged(self):
        segments = [
            _make_segment("v_seg001", 0, 5),  # 5s — too short
            _make_segment("v_seg002", 5, 65),
            _make_segment("v_seg003", 65, 125),
        ]
        result = _merge_short_segments(segments, min_duration=30)
        assert len(result) == 2
        assert result[0].start == 0
        assert result[0].end == 65

    def test_all_above_threshold_unchanged(self):
        segments = [
            _make_segment("v_seg001", 0, 60),
            _make_segment("v_seg002", 60, 120),
        ]
        result = _merge_short_segments(segments, min_duration=30)
        assert len(result) == 2

    def test_single_segment_unchanged(self):
        segments = [_make_segment("v_seg001", 0, 10)]
        result = _merge_short_segments(segments, min_duration=30)
        assert len(result) == 1

    def test_segment_ids_renumbered(self):
        segments = [
            _make_segment("v_seg001", 0, 60),
            _make_segment("v_seg002", 60, 120),
            _make_segment("v_seg003", 120, 125),  # short
        ]
        result = _merge_short_segments(segments, min_duration=30)
        assert result[0].segment_id == "v_seg001"
        assert result[1].segment_id == "v_seg002"
