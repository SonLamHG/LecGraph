"""Semantic search engine with vector search + graph enrichment."""

from rich.console import Console

from src.db.chroma_client import COLLECTION_CONCEPTS, COLLECTION_SEGMENTS, get_collection
from src.db.neo4j_client import run_query
from src.pipeline.embeddings import embed_texts
from src.search.models import SearchResponse, SearchResult

console = Console(force_terminal=True)


def _vector_search(
    query_embedding: list[float],
    video_id: str | None,
    limit: int,
) -> list[dict]:
    """Search ChromaDB segments collection by embedding similarity."""
    collection = get_collection(COLLECTION_SEGMENTS)

    where = {"video_id": video_id} if video_id else None
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=limit,
        where=where,
        include=["metadatas", "documents", "distances"],
    )

    items = []
    if results and results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity score: 1 - (distance / 2) maps [0,2] to [1,0]
            score = max(0.0, 1.0 - distance)
            items.append({
                "segment_id": meta.get("segment_id", doc_id),
                "title": meta.get("title", ""),
                "video_id": meta.get("video_id", ""),
                "video_title": meta.get("video_title", ""),
                "start": meta.get("start", 0.0),
                "end": meta.get("end", 0.0),
                "score": score,
                "transcript": results["documents"][0][i] if results["documents"] else "",
            })

    return items


def _enrich_with_graph(segment_result: dict) -> SearchResult:
    """Enrich a segment search result with graph context from Neo4j."""
    seg_id = segment_result["segment_id"]

    # Get concepts explained in this segment
    concepts = []
    prerequisites = []
    related = []
    examples = []

    try:
        concept_rows = run_query(
            """
            MATCH (c:Concept)-[:EXPLAINED_IN]->(s:Segment {id: $seg_id})
            RETURN c.name AS name
            """,
            {"seg_id": seg_id},
        )
        concepts = [r["name"] for r in concept_rows]

        if concepts:
            # Get prerequisites for these concepts
            prereq_rows = run_query(
                """
                MATCH (c:Concept)-[:EXPLAINED_IN]->(s:Segment {id: $seg_id})
                MATCH (c)-[:DEPENDS_ON]->(prereq:Concept)
                RETURN DISTINCT prereq.name AS name
                """,
                {"seg_id": seg_id},
            )
            prerequisites = [r["name"] for r in prereq_rows]

            # Get related concepts (non-DEPENDS_ON edges)
            related_rows = run_query(
                """
                MATCH (c:Concept)-[:EXPLAINED_IN]->(s:Segment {id: $seg_id})
                MATCH (c)-[r]->(other:Concept)
                WHERE type(r) <> 'DEPENDS_ON' AND type(r) <> 'EXPLAINED_IN'
                RETURN DISTINCT other.name AS name
                """,
                {"seg_id": seg_id},
            )
            related = [r["name"] for r in related_rows]

            # Get examples
            example_rows = run_query(
                """
                MATCH (c:Concept)-[:EXPLAINED_IN]->(s:Segment {id: $seg_id})
                MATCH (e:Example)-[:ILLUSTRATES]->(c)
                RETURN DISTINCT e.description AS description
                """,
                {"seg_id": seg_id},
            )
            examples = [r["description"] for r in example_rows]

    except Exception:
        # If Neo4j is not available, return without enrichment
        pass

    # Truncate transcript for excerpt
    transcript = segment_result.get("transcript", "")
    excerpt = transcript[:500] + "..." if len(transcript) > 500 else transcript

    return SearchResult(
        segment_id=seg_id,
        segment_title=segment_result.get("title", ""),
        video_id=segment_result.get("video_id", ""),
        video_title=segment_result.get("video_title", ""),
        start=segment_result.get("start", 0.0),
        end=segment_result.get("end", 0.0),
        score=segment_result.get("score", 0.0),
        transcript_excerpt=excerpt,
        concepts=concepts,
        prerequisites=prerequisites,
        related_concepts=related,
        examples=examples,
    )


def search(
    query: str,
    video_id: str | None = None,
    limit: int = 10,
) -> SearchResponse:
    """Perform semantic search with graph enrichment.

    Args:
        query: Search query text.
        video_id: Optional video ID to filter results.
        limit: Maximum number of results.

    Returns:
        SearchResponse with enriched results.
    """
    console.print(f"\n[bold blue]Searching:[/] \"{query}\"")

    # Step 1: Embed query
    query_embedding = embed_texts([query])[0]

    # Step 2: Vector search
    raw_results = _vector_search(query_embedding, video_id, limit)
    console.print(f"  [dim]{len(raw_results)} segments found[/]")

    # Step 3: Enrich with graph context
    enriched = [_enrich_with_graph(r) for r in raw_results]

    # Step 4: Sort by score (already sorted from ChromaDB, but ensure)
    enriched.sort(key=lambda r: r.score, reverse=True)

    response = SearchResponse(query=query, results=enriched, total=len(enriched))
    console.print(f"[green]Search complete:[/] {len(enriched)} results")
    return response
