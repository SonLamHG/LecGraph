"""Cross-video concept linking: detect and merge same concepts across videos."""

from rich.console import Console

from src.db.neo4j_client import run_write
from src.pipeline.entity_resolver import resolve_entities
from src.pipeline.models import Concept, KnowledgeUnit, PipelineResult

console = Console(force_terminal=True)


def _collect_all_concepts(
    results: list[PipelineResult],
) -> tuple[list[Concept], dict[str, list[tuple[str, str]]]]:
    """Collect all unique concepts across all videos.

    Returns:
        - List of unique concepts (merged across videos)
        - Dict mapping concept name -> list of (video_id, segment_id) appearances
    """
    concept_appearances: dict[str, list[tuple[str, str]]] = {}
    concept_by_name: dict[str, Concept] = {}

    for result in results:
        for ku in result.knowledge_units:
            for concept in ku.concepts:
                appearances = concept_appearances.setdefault(concept.name, [])
                appearances.append((result.video_id, ku.segment_id))

                if concept.name not in concept_by_name:
                    concept_by_name[concept.name] = concept

    return list(concept_by_name.values()), concept_appearances


def _update_graph(
    resolved_concepts: list[Concept],
    appearances: dict[str, list[tuple[str, str]]],
    name_mapping: dict[str, str],
) -> int:
    """Update Neo4j graph with cross-video links.

    Creates EXPLAINED_IN edges from resolved concepts to all segments
    where they appear across videos.

    Returns:
        Number of cross-video edges created.
    """
    edge_count = 0

    for concept in resolved_concepts:
        # Gather all appearances (including from merged aliases)
        all_appearances: list[tuple[str, str]] = []
        for name in [concept.name] + concept.aliases:
            canonical = name_mapping.get(name, name)
            all_appearances.extend(appearances.get(name, []))
            if canonical != name:
                all_appearances.extend(appearances.get(canonical, []))

        # Deduplicate
        seen = set()
        unique_appearances = []
        for vid_id, seg_id in all_appearances:
            key = (vid_id, seg_id)
            if key not in seen:
                seen.add(key)
                unique_appearances.append((vid_id, seg_id))

        # Create edges for each appearance
        for video_id, segment_id in unique_appearances:
            run_write(
                """
                MERGE (c:Concept {name: $concept_name})
                WITH c
                MATCH (s:Segment {id: $segment_id})
                MERGE (c)-[:EXPLAINED_IN {video_id: $video_id}]->(s)
                """,
                {
                    "concept_name": concept.name,
                    "segment_id": segment_id,
                    "video_id": video_id,
                },
            )
            edge_count += 1

    return edge_count


def link_across_videos(results: list[PipelineResult]) -> dict:
    """Link concepts across multiple videos.

    1. Collect all concepts from all videos
    2. Run entity resolution to find duplicates across videos
    3. Update Neo4j graph with cross-video EXPLAINED_IN edges

    Args:
        results: List of PipelineResult objects from multiple videos.

    Returns:
        Dict with stats: {total_concepts, resolved_concepts, cross_video_edges}
    """
    if len(results) < 2:
        console.print("[yellow]Need at least 2 videos for cross-video linking.[/]")
        return {"total_concepts": 0, "resolved_concepts": 0, "cross_video_edges": 0}

    console.print(
        f"\n[bold blue]Cross-video linking:[/] {len(results)} videos"
    )

    all_concepts, appearances = _collect_all_concepts(results)
    console.print(f"  [dim]{len(all_concepts)} total unique concepts across all videos[/]")

    # Run entity resolution
    resolved = resolve_entities(all_concepts)

    # Build name mapping: original name -> resolved canonical name
    name_mapping: dict[str, str] = {}
    for concept in resolved:
        for alias in [concept.name] + concept.aliases:
            name_mapping[alias] = concept.name

    # Update graph
    edge_count = _update_graph(resolved, appearances, name_mapping)

    stats = {
        "total_concepts": len(all_concepts),
        "resolved_concepts": len(resolved),
        "cross_video_edges": edge_count,
    }
    console.print(f"[green]Cross-video linking complete:[/] {stats}")
    return stats
