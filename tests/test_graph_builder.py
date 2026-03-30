"""Tests for graph_builder module using mocked Neo4j."""

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.graph_builder import (
    _create_concept_nodes,
    _create_example_nodes,
    _create_relationships,
    _create_segment_nodes,
    _create_video_node,
    build_graph,
)
from src.pipeline.models import (
    Concept,
    Example,
    KeyQuote,
    KnowledgeUnit,
    PipelineResult,
    Relationship,
    Segment,
    Sentence,
    TimestampRange,
)


def _make_result() -> PipelineResult:
    """Create a minimal PipelineResult for testing."""
    sentences = [
        Sentence(text="Hello world", start=0.0, end=2.0, confidence=0.9),
        Sentence(text="This is a test", start=2.0, end=4.0, confidence=0.85),
    ]
    segments = [
        Segment(
            segment_id="vid01_seg001",
            title="Introduction",
            start=0.0,
            end=4.0,
            transcript="Hello world. This is a test.",
            sentences=sentences,
        ),
    ]
    concepts = [
        Concept(
            name="Neural Network",
            aliases=["NN"],
            type="definition",
            definition="A computing system inspired by biological neural networks.",
            importance="core",
            timestamp_range=TimestampRange(start=0.0, end=4.0),
        ),
        Concept(
            name="Gradient Descent",
            aliases=["GD"],
            type="algorithm",
            definition="An optimization algorithm.",
            importance="core",
            timestamp_range=TimestampRange(start=0.0, end=4.0),
        ),
    ]
    relationships = [
        Relationship(
            from_concept="Gradient Descent",
            to_concept="Neural Network",
            type="applies_to",
            evidence="GD is used to train neural networks.",
        ),
    ]
    examples = [
        Example(
            description="Image recognition using CNN",
            illustrates="Neural Network",
            timestamp=1.0,
        ),
    ]
    knowledge_units = [
        KnowledgeUnit(
            segment_id="vid01_seg001",
            video_id="vid01",
            title="Introduction",
            timestamp=TimestampRange(start=0.0, end=4.0),
            concepts=concepts,
            relationships=relationships,
            examples=examples,
            key_quotes=[
                KeyQuote(text="Neural networks are powerful.", timestamp=1.5, relevance="Core statement"),
            ],
        ),
    ]

    return PipelineResult(
        video_id="vid01",
        video_title="Test Video",
        source="https://example.com/video",
        duration=4.0,
        segments=segments,
        knowledge_units=knowledge_units,
        unique_concepts=concepts,
    )


@patch("src.pipeline.graph_builder.run_write")
def test_create_video_node(mock_run_write):
    result = _make_result()
    count = _create_video_node(result)
    assert count == 1
    mock_run_write.assert_called_once()
    call_args = mock_run_write.call_args
    assert "MERGE (v:Video" in call_args[0][0]
    assert call_args[0][1]["id"] == "vid01"
    assert call_args[0][1]["title"] == "Test Video"


@patch("src.pipeline.graph_builder.run_write")
def test_create_segment_nodes(mock_run_write):
    result = _make_result()
    count = _create_segment_nodes(result)
    assert count == 1
    assert mock_run_write.call_count == 1
    call_args = mock_run_write.call_args
    assert "MERGE (s:Segment" in call_args[0][0]
    assert call_args[0][1]["id"] == "vid01_seg001"


@patch("src.pipeline.graph_builder.run_write")
def test_create_concept_nodes(mock_run_write):
    result = _make_result()
    count = _create_concept_nodes(result)
    assert count == 2  # 2 unique concepts
    # 2 concept MERGE calls + 2 EXPLAINED_IN edge calls (each concept in 1 segment)
    assert mock_run_write.call_count == 4


@patch("src.pipeline.graph_builder.run_write")
def test_create_relationships(mock_run_write):
    result = _make_result()
    count = _create_relationships(result)
    assert count == 1
    call_args = mock_run_write.call_args
    assert "APPLIES_TO" in call_args[0][0]
    assert call_args[0][1]["from_name"] == "Gradient Descent"
    assert call_args[0][1]["to_name"] == "Neural Network"


@patch("src.pipeline.graph_builder.run_write")
def test_create_example_nodes(mock_run_write):
    result = _make_result()
    count = _create_example_nodes(result)
    assert count == 1
    call_args = mock_run_write.call_args
    assert "MERGE (e:Example" in call_args[0][0]
    assert call_args[0][1]["concept_name"] == "Neural Network"


@patch("src.pipeline.graph_builder.run_write")
@patch("src.pipeline.graph_builder.ensure_constraints")
def test_build_graph_full(mock_constraints, mock_run_write):
    result = _make_result()
    stats = build_graph(result)
    assert stats["videos"] == 1
    assert stats["segments"] == 1
    assert stats["concepts"] == 2
    assert stats["relationships"] == 1
    assert stats["examples"] == 1
    mock_constraints.assert_called_once()


@patch("src.pipeline.graph_builder.run_write")
def test_duplicate_relationships_skipped(mock_run_write):
    """Duplicate relationships should only be created once."""
    result = _make_result()
    # Add a duplicate relationship to second KU
    dup_rel = Relationship(
        from_concept="Gradient Descent",
        to_concept="Neural Network",
        type="applies_to",
        evidence="Duplicate evidence.",
    )
    result.knowledge_units.append(
        KnowledgeUnit(
            segment_id="vid01_seg002",
            video_id="vid01",
            title="Duplicate",
            timestamp=TimestampRange(start=4.0, end=8.0),
            concepts=[],
            relationships=[dup_rel],
            examples=[],
            key_quotes=[],
        )
    )
    count = _create_relationships(result)
    assert count == 1  # Only 1, not 2
