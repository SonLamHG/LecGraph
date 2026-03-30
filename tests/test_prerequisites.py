"""Tests for prerequisites module."""

from unittest.mock import patch

import pytest

from src.search.prerequisites import PrerequisiteNode, PrerequisiteResult, get_prerequisites


@patch("src.search.prerequisites.run_query")
def test_get_prerequisites_basic(mock_run_query):
    mock_run_query.return_value = [
        {"name": "Calculus", "definition": "Branch of math.", "depth": 1,
         "video_id": "v1", "segment_id": "s1", "timestamp_start": 0.0, "timestamp_end": 60.0},
        {"name": "Linear Algebra", "definition": "Study of vectors.", "depth": 2,
         "video_id": "v1", "segment_id": "s2", "timestamp_start": 60.0, "timestamp_end": 120.0},
    ]

    result = get_prerequisites("Gradient Descent")

    assert isinstance(result, PrerequisiteResult)
    assert result.concept == "Gradient Descent"
    assert len(result.prerequisites) == 2
    assert result.prerequisites[0].name == "Calculus"
    assert result.prerequisites[0].depth == 1
    assert result.max_depth == 2


@patch("src.search.prerequisites.run_query")
def test_get_prerequisites_empty(mock_run_query):
    mock_run_query.return_value = []

    result = get_prerequisites("Basic Concept")
    assert len(result.prerequisites) == 0
    assert result.max_depth == 0


@patch("src.search.prerequisites.run_query")
def test_get_prerequisites_deduplicates(mock_run_query):
    """Same concept appearing in multiple segments should be deduplicated."""
    mock_run_query.return_value = [
        {"name": "Math", "definition": "Mathematics.", "depth": 1,
         "video_id": "v1", "segment_id": "s1", "timestamp_start": 0.0, "timestamp_end": 30.0},
        {"name": "Math", "definition": "Mathematics.", "depth": 1,
         "video_id": "v2", "segment_id": "s2", "timestamp_start": 0.0, "timestamp_end": 30.0},
    ]

    result = get_prerequisites("AI")
    assert len(result.prerequisites) == 1  # Deduplicated


def test_prerequisite_node_model():
    node = PrerequisiteNode(
        name="Test", definition="A test.", depth=1,
        video_id="v1", segment_id="s1",
        timestamp_start=0.0, timestamp_end=10.0,
    )
    assert node.name == "Test"
    data = node.model_dump()
    assert data["depth"] == 1
