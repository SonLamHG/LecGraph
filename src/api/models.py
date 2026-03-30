"""API request/response models."""

from pydantic import BaseModel


# --- Requests ---

class VideoCreate(BaseModel):
    source: str  # URL or file path


class SearchRequest(BaseModel):
    query: str
    video_id: str | None = None
    limit: int = 10


class LearningPathRequest(BaseModel):
    target_concept: str
    known_concepts: list[str] = []


# --- Responses ---

class VideoResponse(BaseModel):
    id: str
    title: str
    source: str
    duration: float
    status: str = "completed"


class SegmentResponse(BaseModel):
    id: str
    video_id: str
    title: str
    start: float
    end: float


class ConceptResponse(BaseModel):
    name: str
    aliases: list[str] = []
    type: str
    definition: str
    importance: str


class ConceptDetailResponse(ConceptResponse):
    relationships: list[dict] = []
    segments: list[dict] = []


class StatusResponse(BaseModel):
    status: str
    message: str = ""
