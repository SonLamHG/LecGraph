"""Search routes."""

from fastapi import APIRouter

from src.api.models import SearchRequest
from src.search.engine import search

router = APIRouter()


@router.post("")
async def semantic_search(body: SearchRequest):
    """Perform semantic search with graph enrichment."""
    result = search(body.query, video_id=body.video_id, limit=body.limit)
    return result.model_dump()
