"""Tests for search engine."""

from unittest.mock import MagicMock, patch

import pytest

from src.search.engine import _enrich_with_graph, _vector_search, search
from src.search.models import SearchResponse, SearchResult


@patch("src.search.engine.get_collection")
def test_vector_search_basic(mock_get_collection):
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection
    mock_collection.query.return_value = {
        "ids": [["seg001", "seg002"]],
        "metadatas": [[
            {"segment_id": "seg001", "title": "Intro", "video_id": "v1",
             "video_title": "Test", "start": 0.0, "end": 10.0},
            {"segment_id": "seg002", "title": "Main", "video_id": "v1",
             "video_title": "Test", "start": 10.0, "end": 20.0},
        ]],
        "documents": [["Transcript 1", "Transcript 2"]],
        "distances": [[0.5, 1.0]],
    }

    results = _vector_search([0.1, 0.2, 0.3], None, 10)
    assert len(results) == 2
    assert results[0]["segment_id"] == "seg001"
    assert results[0]["score"] > results[1]["score"]


@patch("src.search.engine.get_collection")
def test_vector_search_with_video_filter(mock_get_collection):
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection
    mock_collection.query.return_value = {
        "ids": [[]], "metadatas": [[]], "documents": [[]], "distances": [[]],
    }

    _vector_search([0.1], "v1", 5)
    call_kwargs = mock_collection.query.call_args[1]
    assert call_kwargs["where"] == {"video_id": "v1"}


@patch("src.search.engine.run_query")
def test_enrich_with_graph(mock_run_query):
    # Mock Neo4j responses
    mock_run_query.side_effect = [
        [{"name": "AI"}, {"name": "ML"}],  # concepts
        [{"name": "Math"}],  # prerequisites
        [{"name": "DL"}],  # related
        [{"description": "Example 1"}],  # examples
    ]

    segment_data = {
        "segment_id": "seg001",
        "title": "Intro",
        "video_id": "v1",
        "video_title": "Test Video",
        "start": 0.0,
        "end": 10.0,
        "score": 0.85,
        "transcript": "Some transcript text",
    }

    result = _enrich_with_graph(segment_data)
    assert isinstance(result, SearchResult)
    assert result.concepts == ["AI", "ML"]
    assert result.prerequisites == ["Math"]
    assert result.related_concepts == ["DL"]
    assert result.examples == ["Example 1"]


@patch("src.search.engine.run_query")
def test_enrich_with_graph_neo4j_unavailable(mock_run_query):
    """Should gracefully handle Neo4j being unavailable."""
    mock_run_query.side_effect = Exception("Connection refused")

    segment_data = {
        "segment_id": "seg001",
        "title": "Intro",
        "video_id": "v1",
        "video_title": "Test",
        "start": 0.0,
        "end": 10.0,
        "score": 0.9,
        "transcript": "text",
    }

    result = _enrich_with_graph(segment_data)
    assert result.concepts == []
    assert result.prerequisites == []


@patch("src.search.engine._enrich_with_graph")
@patch("src.search.engine._vector_search")
@patch("src.search.engine.embed_texts")
def test_search_full(mock_embed, mock_vector, mock_enrich):
    mock_embed.return_value = [[0.1, 0.2]]
    mock_vector.return_value = [
        {"segment_id": "seg001", "title": "T", "video_id": "v1",
         "video_title": "V", "start": 0.0, "end": 5.0, "score": 0.9,
         "transcript": "text"},
    ]
    mock_enrich.return_value = SearchResult(
        segment_id="seg001", segment_title="T", video_id="v1",
        video_title="V", start=0.0, end=5.0, score=0.9,
        transcript_excerpt="text",
    )

    response = search("gradient descent", limit=5)
    assert isinstance(response, SearchResponse)
    assert response.total == 1
    assert response.results[0].segment_id == "seg001"
    mock_embed.assert_called_once_with(["gradient descent"])


def test_search_response_model():
    """Test that SearchResponse serializes correctly."""
    result = SearchResult(
        segment_id="s1", segment_title="Title", video_id="v1",
        video_title="Video", start=0.0, end=10.0, score=0.95,
        transcript_excerpt="excerpt",
        concepts=["AI"], prerequisites=["Math"],
        related_concepts=["ML"], examples=["ex1"],
    )
    response = SearchResponse(query="test", results=[result], total=1)
    data = response.model_dump()
    assert data["query"] == "test"
    assert len(data["results"]) == 1
    assert data["results"][0]["score"] == 0.95
