"""Index pipeline results into ChromaDB for semantic search."""

import json
from pathlib import Path

from rich.console import Console

from src.db.chroma_client import COLLECTION_CONCEPTS, COLLECTION_SEGMENTS, get_collection
from src.pipeline.embeddings import embed_texts
from src.pipeline.models import PipelineResult
from src.pipeline.postprocessor import _normalize_name

console = Console(force_terminal=True)


def _index_segments(result: PipelineResult) -> int:
    """Index all segments into ChromaDB. Returns count."""
    collection = get_collection(COLLECTION_SEGMENTS)

    ids = []
    documents = []
    metadatas = []

    for seg in result.segments:
        ids.append(seg.segment_id)
        documents.append(seg.transcript)
        metadatas.append({
            "video_id": result.video_id,
            "video_title": result.video_title,
            "segment_id": seg.segment_id,
            "title": seg.title,
            "start": seg.start,
            "end": seg.end,
        })

    if not ids:
        return 0

    embeddings = embed_texts(documents)
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    return len(ids)


def _index_concepts(result: PipelineResult) -> int:
    """Index all unique concepts into ChromaDB. Returns count."""
    collection = get_collection(COLLECTION_CONCEPTS)

    ids = []
    documents = []
    metadatas = []

    for concept in result.unique_concepts:
        doc_id = f"concept_{_normalize_name(concept.name)}"
        doc_text = f"{concept.name}: {concept.definition}"

        ids.append(doc_id)
        documents.append(doc_text)
        metadatas.append({
            "name": concept.name,
            "type": concept.type,
            "importance": concept.importance,
            "aliases": json.dumps(concept.aliases),
            "video_id": result.video_id,
        })

    if not ids:
        return 0

    embeddings = embed_texts(documents)
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    return len(ids)


def index_pipeline_result(result: PipelineResult) -> dict:
    """Index a PipelineResult into ChromaDB (segments + concepts).

    Returns:
        Dict with counts: {segments, concepts}
    """
    console.print(f"\n[bold blue]Indexing into ChromaDB:[/] {result.video_title}")

    seg_count = _index_segments(result)
    console.print(f"  [dim]{seg_count} segments indexed[/]")

    concept_count = _index_concepts(result)
    console.print(f"  [dim]{concept_count} concepts indexed[/]")

    stats = {"segments": seg_count, "concepts": concept_count}
    console.print(f"[green]Indexing complete:[/] {stats}")
    return stats


def index_from_json(json_path: str) -> dict:
    """Load a PipelineResult JSON file and index it.

    Args:
        json_path: Path to the JSON file from Phase 1 pipeline output.

    Returns:
        Dict with indexed counts.
    """
    path = Path(json_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    result = PipelineResult.model_validate(data)
    return index_pipeline_result(result)
