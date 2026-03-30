"""Search response models."""

from pydantic import BaseModel


class SearchResult(BaseModel):
    """A single search result with graph-enriched context."""
    segment_id: str
    segment_title: str
    video_id: str
    video_title: str
    start: float
    end: float
    score: float
    transcript_excerpt: str
    concepts: list[str] = []
    prerequisites: list[str] = []
    related_concepts: list[str] = []
    examples: list[str] = []


class SearchResponse(BaseModel):
    """Complete search response."""
    query: str
    results: list[SearchResult]
    total: int
