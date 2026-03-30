"""FastAPI application for LecGraph."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import graph, learning_path, search, videos
from src.config import settings
from src.db.neo4j_client import close_driver, ensure_constraints


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    ensure_constraints()
    yield
    # Shutdown
    close_driver()


app = FastAPI(
    title="LecGraph API",
    description="Transform lecture videos into searchable knowledge graphs",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(learning_path.router, prefix="/api/learning-path", tags=["learning-path"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
