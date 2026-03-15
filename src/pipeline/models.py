"""Data models for the LecGraph pipeline."""

from pydantic import BaseModel


# --- Stage 1: Transcription ---

class Word(BaseModel):
    """A single word with timestamp from Whisper."""
    text: str
    start: float
    end: float
    confidence: float


class Sentence(BaseModel):
    """A sentence grouped from words, with start/end timestamps."""
    text: str
    start: float
    end: float
    confidence: float  # average confidence of words


# --- Stage 2: Segmentation ---

class Segment(BaseModel):
    """A topic-coherent segment of the transcript."""
    segment_id: str
    title: str
    start: float
    end: float
    transcript: str
    sentences: list[Sentence]


# --- Stage 3: Knowledge Extraction ---

class TimestampRange(BaseModel):
    start: float
    end: float


class Concept(BaseModel):
    """A knowledge concept extracted from a segment."""
    name: str
    aliases: list[str] = []
    type: str  # definition, algorithm, theorem, technique, property
    definition: str
    importance: str  # core, supporting, mentioned
    timestamp_range: TimestampRange | None = None


class Relationship(BaseModel):
    """A relationship between two concepts."""
    from_concept: str
    to_concept: str
    type: str  # depends_on, extends, is_part_of, illustrates, contrasts, hyperparameter_of, applies_to
    evidence: str


class Example(BaseModel):
    """An example or illustration found in the segment."""
    description: str
    illustrates: str  # concept name
    timestamp: float | None = None


class KeyQuote(BaseModel):
    """A notable quote from the lecture."""
    text: str
    timestamp: float | None = None
    relevance: str


class KnowledgeUnit(BaseModel):
    """Complete knowledge extraction for one segment."""
    segment_id: str
    video_id: str
    title: str
    timestamp: TimestampRange
    concepts: list[Concept]
    relationships: list[Relationship]
    examples: list[Example]
    key_quotes: list[KeyQuote]


# --- Pipeline Result ---

class PipelineResult(BaseModel):
    """Complete result of processing one video."""
    video_id: str
    video_title: str
    source: str
    duration: float
    segments: list[Segment]
    knowledge_units: list[KnowledgeUnit]
