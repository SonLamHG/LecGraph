"""Shared embedding model singleton for the LecGraph pipeline."""

import threading

import numpy as np
from rich.console import Console

from src.config import settings

console = Console(force_terminal=True)

_model = None
_model_lock = threading.Lock()


def get_embedding_model():
    """Get or create the sentence-transformers model (thread-safe singleton)."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                console.print(
                    f"[bold blue]Loading embedding model:[/] {settings.embedding_model}"
                )
                _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Embed a list of texts into vectors.

    Args:
        texts: List of strings to embed.
        batch_size: Batch size for encoding.

    Returns:
        List of embedding vectors (each a list of floats).
    """
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False, batch_size=batch_size)
    return np.array(embeddings).tolist()
