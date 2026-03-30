"""Learning path routes."""

from fastapi import APIRouter

from src.api.models import LearningPathRequest
from src.search.learning_path import generate_learning_path

router = APIRouter()


@router.post("")
async def create_learning_path(body: LearningPathRequest):
    """Generate a learning path for a target concept."""
    result = generate_learning_path(
        body.target_concept,
        known_concepts=body.known_concepts,
    )
    return result.model_dump()
