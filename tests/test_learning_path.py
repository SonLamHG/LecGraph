"""Tests for learning_path module."""

from unittest.mock import patch

import pytest

from src.search.learning_path import (
    LearningPath,
    LearningStep,
    _topological_sort,
    generate_learning_path,
)


class TestTopologicalSort:
    def test_linear_chain(self):
        """A -> B -> C should produce [C, B, A]."""
        adjacency = {"A": ["B"], "B": ["C"]}
        all_nodes = {"A", "B", "C"}
        result = _topological_sort(adjacency, all_nodes)
        # C has no deps, then B (depends on C), then A (depends on B)
        assert result.index("C") < result.index("B")
        assert result.index("B") < result.index("A")

    def test_diamond(self):
        """A depends on B and C, both depend on D."""
        adjacency = {"A": ["B", "C"], "B": ["D"], "C": ["D"]}
        all_nodes = {"A", "B", "C", "D"}
        result = _topological_sort(adjacency, all_nodes)
        assert result.index("D") < result.index("B")
        assert result.index("D") < result.index("C")
        assert result.index("B") < result.index("A")
        assert result.index("C") < result.index("A")

    def test_no_dependencies(self):
        """Independent nodes should all appear."""
        adjacency = {}
        all_nodes = {"A", "B", "C"}
        result = _topological_sort(adjacency, all_nodes)
        assert set(result) == {"A", "B", "C"}

    def test_single_node(self):
        result = _topological_sort({}, {"X"})
        assert result == ["X"]

    def test_empty(self):
        result = _topological_sort({}, set())
        assert result == []


@patch("src.search.learning_path.run_query")
def test_generate_learning_path_basic(mock_run_query):
    # First call: get all concepts + info
    mock_run_query.side_effect = [
        # _build_dependency_graph: concept info query
        [
            {"name": "CNN", "definition": "Convolutional Neural Network.", "depth": 0,
             "video_id": "v1", "video_title": "DL Course", "segment_id": "s3",
             "timestamp_start": 100.0, "timestamp_end": 200.0},
            {"name": "Neural Network", "definition": "A network of neurons.", "depth": 1,
             "video_id": "v1", "video_title": "DL Course", "segment_id": "s1",
             "timestamp_start": 0.0, "timestamp_end": 60.0},
            {"name": "Linear Algebra", "definition": "Vectors and matrices.", "depth": 2,
             "video_id": "v1", "video_title": "DL Course", "segment_id": "s0",
             "timestamp_start": 0.0, "timestamp_end": 30.0},
        ],
        # _build_dependency_graph: edge query
        [
            {"from_concept": "CNN", "to_concept": "Neural Network"},
            {"from_concept": "Neural Network", "to_concept": "Linear Algebra"},
        ],
    ]

    result = generate_learning_path("CNN")

    assert isinstance(result, LearningPath)
    assert result.target_concept == "CNN"
    assert len(result.steps) == 3

    # Should be in learning order: Linear Algebra -> Neural Network -> CNN
    names = [s.concept for s in result.steps]
    assert names.index("Linear Algebra") < names.index("Neural Network")
    assert names.index("Neural Network") < names.index("CNN")


@patch("src.search.learning_path.run_query")
def test_generate_learning_path_with_known(mock_run_query):
    mock_run_query.side_effect = [
        [
            {"name": "CNN", "definition": "CNN.", "depth": 0,
             "video_id": "v1", "video_title": "V", "segment_id": "s3",
             "timestamp_start": 100.0, "timestamp_end": 200.0},
            {"name": "Neural Network", "definition": "NN.", "depth": 1,
             "video_id": "v1", "video_title": "V", "segment_id": "s1",
             "timestamp_start": 0.0, "timestamp_end": 60.0},
            {"name": "Linear Algebra", "definition": "LA.", "depth": 2,
             "video_id": "v1", "video_title": "V", "segment_id": "s0",
             "timestamp_start": 0.0, "timestamp_end": 30.0},
        ],
        [
            {"from_concept": "CNN", "to_concept": "Neural Network"},
            {"from_concept": "Neural Network", "to_concept": "Linear Algebra"},
        ],
    ]

    result = generate_learning_path("CNN", known_concepts=["Linear Algebra"])

    names = [s.concept for s in result.steps]
    assert "Linear Algebra" not in names
    assert "CNN" in names
    assert "Linear Algebra" in result.known_concepts_skipped


@patch("src.search.learning_path.run_query")
def test_generate_learning_path_no_prereqs(mock_run_query):
    mock_run_query.side_effect = [
        [
            {"name": "Basics", "definition": "Basic stuff.", "depth": 0,
             "video_id": "v1", "video_title": "V", "segment_id": "s1",
             "timestamp_start": 0.0, "timestamp_end": 30.0},
        ],
        [],  # No edges
    ]

    result = generate_learning_path("Basics")
    assert len(result.steps) == 1
    assert result.steps[0].concept == "Basics"


@patch("src.search.learning_path.run_query")
def test_generate_learning_path_empty(mock_run_query):
    mock_run_query.side_effect = [[], []]

    result = generate_learning_path("NonExistent")
    assert len(result.steps) == 0
    assert result.estimated_total_time == 0.0


def test_learning_step_model():
    step = LearningStep(
        concept="AI", definition="Artificial Intelligence.",
        video_id="v1", video_title="Intro to AI",
        segment_id="s1", timestamp_start=0.0, timestamp_end=60.0,
        estimated_duration=60.0,
    )
    assert step.estimated_duration == 60.0
