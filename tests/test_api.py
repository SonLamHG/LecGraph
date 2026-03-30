"""Tests for FastAPI endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with mocked Neo4j."""
    with patch("src.db.neo4j_client.get_driver") as mock_driver, \
         patch("src.db.neo4j_client.ensure_constraints"):
        mock_driver.return_value = MagicMock()
        from src.api.main import app
        with TestClient(app) as c:
            yield c


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("src.api.routes.videos.run_query")
def test_list_videos(mock_query, client):
    mock_query.return_value = [
        {"id": "v1", "title": "Video 1", "source": "test.mp4",
         "duration": 60.0, "status": "completed"},
    ]

    response = client.get("/api/videos")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "v1"


@patch("src.api.routes.videos.run_write")
def test_create_video(mock_write, client):
    response = client.post("/api/videos", json={"source": "https://youtube.com/watch?v=test"})
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["source"] == "https://youtube.com/watch?v=test"
    mock_write.assert_called_once()


@patch("src.api.routes.videos.run_query")
def test_get_video_segments(mock_query, client):
    mock_query.return_value = [
        {"id": "v1_seg001", "video_id": "v1", "title": "Intro",
         "start": 0.0, "end": 30.0},
    ]

    response = client.get("/api/videos/v1/segments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "v1_seg001"


@patch("src.api.routes.videos.run_query")
def test_get_video_segments_not_found(mock_query, client):
    mock_query.return_value = []
    response = client.get("/api/videos/nonexistent/segments")
    assert response.status_code == 404


@patch("src.api.routes.graph.run_query")
def test_list_concepts(mock_query, client):
    mock_query.return_value = [
        {"name": "AI", "aliases": ["Artificial Intelligence"], "type": "definition",
         "definition": "AI field.", "importance": "core"},
    ]

    response = client.get("/api/graph/concepts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "AI"


@patch("src.api.routes.graph.run_query")
def test_list_concepts_pagination(mock_query, client):
    mock_query.return_value = []
    response = client.get("/api/graph/concepts?skip=10&limit=5")
    assert response.status_code == 200
    call_args = mock_query.call_args
    assert call_args[0][1]["skip"] == 10
    assert call_args[0][1]["limit"] == 5


@patch("src.api.routes.graph.run_query")
def test_get_concept_detail(mock_query, client):
    mock_query.side_effect = [
        # Concept lookup
        [{"c": {"name": "AI", "aliases": [], "type": "definition",
                "definition": "AI field.", "importance": "core"}}],
        # Relationships
        [{"rel_type": "DEPENDS_ON", "target": "Math", "evidence": "needs math"}],
        # Segments
        [{"segment_id": "s1", "title": "Intro", "video_id": "v1",
          "video_title": "Video", "start": 0.0, "end": 30.0}],
    ]

    response = client.get("/api/graph/concepts/AI")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "AI"
    assert len(data["relationships"]) == 1
    assert len(data["segments"]) == 1


@patch("src.api.routes.graph.run_query")
def test_get_concept_not_found(mock_query, client):
    mock_query.return_value = []
    response = client.get("/api/graph/concepts/NonExistent")
    assert response.status_code == 404


@patch("src.api.routes.graph.get_prerequisites")
def test_get_prerequisites_endpoint(mock_prereqs, client):
    from src.search.prerequisites import PrerequisiteNode, PrerequisiteResult
    mock_prereqs.return_value = PrerequisiteResult(
        concept="CNN",
        prerequisites=[
            PrerequisiteNode(name="NN", definition="Neural Network.", depth=1),
        ],
        max_depth=1,
    )

    response = client.get("/api/graph/concepts/CNN/prerequisites")
    assert response.status_code == 200
    data = response.json()
    assert data["concept"] == "CNN"
    assert len(data["prerequisites"]) == 1


@patch("src.api.routes.search.search")
def test_search_endpoint(mock_search, client):
    from src.search.models import SearchResponse, SearchResult
    mock_search.return_value = SearchResponse(
        query="gradient descent",
        results=[
            SearchResult(
                segment_id="s1", segment_title="GD", video_id="v1",
                video_title="ML Course", start=0.0, end=60.0,
                score=0.9, transcript_excerpt="about gradient descent",
            ),
        ],
        total=1,
    )

    response = client.post("/api/search", json={"query": "gradient descent"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["score"] == 0.9


@patch("src.api.routes.learning_path.generate_learning_path")
def test_learning_path_endpoint(mock_generate, client):
    from src.search.learning_path import LearningPath, LearningStep
    mock_generate.return_value = LearningPath(
        target_concept="CNN",
        steps=[
            LearningStep(concept="Math", definition="Mathematics.", estimated_duration=60.0),
            LearningStep(concept="NN", definition="Neural Network.", estimated_duration=120.0),
            LearningStep(concept="CNN", definition="Conv NN.", estimated_duration=180.0),
        ],
        estimated_total_time=360.0,
    )

    response = client.post("/api/learning-path", json={
        "target_concept": "CNN",
        "known_concepts": [],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["target_concept"] == "CNN"
    assert len(data["steps"]) == 3
    assert data["estimated_total_time"] == 360.0
