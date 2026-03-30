"""ChromaDB client with thread-safe singleton."""

import threading

import chromadb
from rich.console import Console

from src.config import settings

console = Console(force_terminal=True)

_client = None
_client_lock = threading.Lock()

COLLECTION_SEGMENTS = "segments"
COLLECTION_CONCEPTS = "concepts"


def get_client() -> chromadb.ClientAPI:
    """Get or create the ChromaDB persistent client (thread-safe)."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = chromadb.PersistentClient(
                    path=settings.chroma_persist_dir,
                )
                console.print(
                    f"[bold blue]ChromaDB initialized:[/] {settings.chroma_persist_dir}"
                )
    return _client


def get_collection(name: str) -> chromadb.Collection:
    """Get or create a ChromaDB collection with cosine distance."""
    client = get_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )
