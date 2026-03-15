"""Tests for pipeline data models."""

import json

from src.pipeline.models import (
    Concept,
    KnowledgeUnit,
    PipelineResult,
    Relationship,
    Segment,
    Sentence,
    TimestampRange,
)


class TestSentence:
    def test_create(self):
        s = Sentence(text="Hello world", start=0.0, end=1.5, confidence=0.95)
        assert s.text == "Hello world"
        assert s.start == 0.0
        assert s.end == 1.5

    def test_serialization_roundtrip(self):
        s = Sentence(text="Test", start=1.0, end=2.0, confidence=0.9)
        data = s.model_dump()
        s2 = Sentence.model_validate(data)
        assert s == s2


class TestSegment:
    def test_create_with_sentences(self):
        sentences = [
            Sentence(text="First sentence.", start=0.0, end=2.0, confidence=0.9),
            Sentence(text="Second sentence.", start=2.5, end=4.0, confidence=0.85),
        ]
        seg = Segment(
            segment_id="vid01_seg001",
            title="Intro",
            start=0.0,
            end=4.0,
            transcript="First sentence. Second sentence.",
            sentences=sentences,
        )
        assert len(seg.sentences) == 2
        assert seg.segment_id == "vid01_seg001"


class TestKnowledgeUnit:
    def test_full_knowledge_unit(self):
        ku = KnowledgeUnit(
            segment_id="vid01_seg001",
            video_id="vid01",
            title="Gradient Descent Basics",
            timestamp=TimestampRange(start=0.0, end=300.0),
            concepts=[
                Concept(
                    name="Gradient Descent",
                    aliases=["GD"],
                    type="algorithm",
                    definition="An optimization algorithm",
                    importance="core",
                ),
            ],
            relationships=[
                Relationship(
                    from_concept="Gradient Descent",
                    to_concept="Derivative",
                    type="depends_on",
                    evidence="Requires understanding of derivatives",
                ),
            ],
            examples=[],
            key_quotes=[],
        )
        assert len(ku.concepts) == 1
        assert len(ku.relationships) == 1
        assert ku.concepts[0].name == "Gradient Descent"


class TestPipelineResult:
    def test_json_roundtrip(self):
        result = PipelineResult(
            video_id="vid01",
            video_title="Test Video",
            source="test.mp4",
            duration=600.0,
            segments=[],
            knowledge_units=[],
        )
        json_str = result.model_dump_json()
        restored = PipelineResult.model_validate_json(json_str)
        assert restored.video_id == "vid01"
        assert restored.video_title == "Test Video"
