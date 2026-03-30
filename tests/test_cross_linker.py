"""Tests for cross_linker module."""

from unittest.mock import patch

import pytest

from src.pipeline.cross_linker import _collect_all_concepts, link_across_videos
from src.pipeline.models import (
    Concept,
    KnowledgeUnit,
    PipelineResult,
    Segment,
    Sentence,
    TimestampRange,
)


def _make_result(video_id: str, concepts: list[Concept]) -> PipelineResult:
    """Create a minimal PipelineResult."""
    sentences = [Sentence(text="Test", start=0.0, end=2.0, confidence=0.9)]
    segments = [
        Segment(
            segment_id=f"{video_id}_seg001",
            title="Segment 1",
            start=0.0,
            end=2.0,
            transcript="Test transcript",
            sentences=sentences,
        ),
    ]
    knowledge_units = [
        KnowledgeUnit(
            segment_id=f"{video_id}_seg001",
            video_id=video_id,
            title="Segment 1",
            timestamp=TimestampRange(start=0.0, end=2.0),
            concepts=concepts,
            relationships=[],
            examples=[],
            key_quotes=[],
        ),
    ]
    return PipelineResult(
        video_id=video_id,
        video_title=f"Video {video_id}",
        source=f"test_{video_id}.mp4",
        duration=2.0,
        segments=segments,
        knowledge_units=knowledge_units,
        unique_concepts=concepts,
    )


def test_collect_all_concepts():
    """Should collect concepts from multiple videos."""
    concepts_v1 = [
        Concept(name="AI", aliases=[], type="definition",
                definition="Artificial Intelligence.", importance="core"),
        Concept(name="ML", aliases=[], type="definition",
                definition="Machine Learning.", importance="core"),
    ]
    concepts_v2 = [
        Concept(name="AI", aliases=[], type="definition",
                definition="AI from video 2.", importance="supporting"),
        Concept(name="DL", aliases=[], type="definition",
                definition="Deep Learning.", importance="core"),
    ]
    r1 = _make_result("vid01", concepts_v1)
    r2 = _make_result("vid02", concepts_v2)

    all_concepts, appearances = _collect_all_concepts([r1, r2])

    assert len(all_concepts) == 3  # AI, ML, DL (AI deduplicated by name)
    assert "AI" in appearances
    assert len(appearances["AI"]) == 2  # Appears in both videos


def test_collect_all_concepts_single_video():
    concepts = [
        Concept(name="AI", aliases=[], type="definition",
                definition="Artificial Intelligence.", importance="core"),
    ]
    r1 = _make_result("vid01", concepts)

    all_concepts, appearances = _collect_all_concepts([r1])
    assert len(all_concepts) == 1
    assert len(appearances["AI"]) == 1


@patch("src.pipeline.cross_linker.run_write")
@patch("src.pipeline.cross_linker.resolve_entities")
def test_link_across_videos(mock_resolve, mock_run_write):
    """Full cross-video linking flow."""
    concepts_v1 = [
        Concept(name="AI", aliases=[], type="definition",
                definition="Artificial Intelligence.", importance="core"),
    ]
    concepts_v2 = [
        Concept(name="AI", aliases=[], type="definition",
                definition="AI from video 2.", importance="supporting"),
        Concept(name="DL", aliases=[], type="definition",
                definition="Deep Learning.", importance="core"),
    ]
    r1 = _make_result("vid01", concepts_v1)
    r2 = _make_result("vid02", concepts_v2)

    # Mock entity resolution returns same concepts (no new merges)
    mock_resolve.return_value = [
        Concept(name="AI", aliases=[], type="definition",
                definition="Artificial Intelligence.", importance="core"),
        Concept(name="DL", aliases=[], type="definition",
                definition="Deep Learning.", importance="core"),
    ]

    stats = link_across_videos([r1, r2])

    assert stats["total_concepts"] == 2  # AI (deduped), DL
    assert stats["resolved_concepts"] == 2
    assert stats["cross_video_edges"] > 0
    mock_run_write.assert_called()


def test_link_single_video_skipped():
    """Single video should skip linking."""
    r1 = _make_result("vid01", [])
    stats = link_across_videos([r1])
    assert stats["total_concepts"] == 0
