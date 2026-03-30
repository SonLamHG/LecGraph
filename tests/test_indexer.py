"""Tests for indexer module using mocked ChromaDB and embeddings."""

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.indexer import _index_concepts, _index_segments, index_pipeline_result
from src.pipeline.models import (
    Concept,
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
    ]
    segments = [
        Segment(
            segment_id="vid01_seg001",
            title="Intro",
            start=0.0,
            end=2.0,
            transcript="Hello world",
            sentences=sentences,
        ),
        Segment(
            segment_id="vid01_seg002",
            title="Main",
            start=2.0,
            end=5.0,
            transcript="Main content here",
            sentences=[Sentence(text="Main content here", start=2.0, end=5.0, confidence=0.85)],
        ),
    ]
    concepts = [
        Concept(
            name="Neural Network",
            aliases=["NN"],
            type="definition",
            definition="A model inspired by biological neurons.",
            importance="core",
        ),
        Concept(
            name="Gradient Descent",
            aliases=[],
            type="algorithm",
            definition="An optimization algorithm.",
            importance="supporting",
        ),
    ]
    knowledge_units = [
        KnowledgeUnit(
            segment_id="vid01_seg001",
            video_id="vid01",
            title="Intro",
            timestamp=TimestampRange(start=0.0, end=2.0),
            concepts=concepts[:1],
            relationships=[],
            examples=[],
            key_quotes=[],
        ),
    ]
    return PipelineResult(
        video_id="vid01",
        video_title="Test Video",
        source="test.mp4",
        duration=5.0,
        segments=segments,
        knowledge_units=knowledge_units,
        unique_concepts=concepts,
    )


@patch("src.pipeline.indexer.embed_texts")
@patch("src.pipeline.indexer.get_collection")
def test_index_segments(mock_get_collection, mock_embed):
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection
    mock_embed.return_value = [[0.1, 0.2], [0.3, 0.4]]

    result = _make_result()
    count = _index_segments(result)

    assert count == 2
    mock_collection.upsert.assert_called_once()
    call_kwargs = mock_collection.upsert.call_args[1]
    assert len(call_kwargs["ids"]) == 2
    assert call_kwargs["ids"][0] == "vid01_seg001"
    assert call_kwargs["metadatas"][0]["video_id"] == "vid01"


@patch("src.pipeline.indexer.embed_texts")
@patch("src.pipeline.indexer.get_collection")
def test_index_concepts(mock_get_collection, mock_embed):
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection
    mock_embed.return_value = [[0.1, 0.2], [0.3, 0.4]]

    result = _make_result()
    count = _index_concepts(result)

    assert count == 2
    mock_collection.upsert.assert_called_once()
    call_kwargs = mock_collection.upsert.call_args[1]
    assert len(call_kwargs["ids"]) == 2
    # Verify concept document format
    assert "Neural Network:" in call_kwargs["documents"][0]


@patch("src.pipeline.indexer.embed_texts")
@patch("src.pipeline.indexer.get_collection")
def test_index_pipeline_result(mock_get_collection, mock_embed):
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection
    mock_embed.return_value = [[0.1, 0.2], [0.3, 0.4]]

    result = _make_result()
    stats = index_pipeline_result(result)

    assert stats["segments"] == 2
    assert stats["concepts"] == 2


@patch("src.pipeline.indexer.embed_texts")
@patch("src.pipeline.indexer.get_collection")
def test_index_empty_result(mock_get_collection, mock_embed):
    """Empty result should not call upsert."""
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection

    result = PipelineResult(
        video_id="vid02",
        video_title="Empty",
        source="empty.mp4",
        duration=0.0,
        segments=[],
        knowledge_units=[],
        unique_concepts=[],
    )
    stats = index_pipeline_result(result)

    assert stats["segments"] == 0
    assert stats["concepts"] == 0
    mock_embed.assert_not_called()
