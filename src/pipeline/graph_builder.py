"""Build Neo4j knowledge graph from PipelineResult."""

import json
from pathlib import Path

from rich.console import Console

from src.db.neo4j_client import ensure_constraints, run_write, run_write_batch
from src.pipeline.models import PipelineResult

console = Console(force_terminal=True)


def _create_video_node(result: PipelineResult) -> int:
    """Create or merge Video node. Returns 1 if created."""
    run_write(
        """
        MERGE (v:Video {id: $id})
        SET v.title = $title,
            v.source = $source,
            v.duration = $duration
        """,
        {
            "id": result.video_id,
            "title": result.video_title,
            "source": result.source,
            "duration": result.duration,
        },
    )
    return 1


def _create_segment_nodes(result: PipelineResult) -> int:
    """Create Segment nodes with BELONGS_TO edges to Video. Returns count."""
    batch_params = [
        {
            "id": seg.segment_id,
            "video_id": result.video_id,
            "title": seg.title,
            "start": seg.start,
            "end": seg.end,
            "transcript": seg.transcript,
        }
        for seg in result.segments
    ]
    run_write_batch(
        """
        MERGE (s:Segment {id: $id})
        SET s.video_id = $video_id,
            s.title = $title,
            s.start = $start,
            s.end = $end,
            s.transcript = $transcript
        WITH s
        MATCH (v:Video {id: $video_id})
        MERGE (s)-[:BELONGS_TO]->(v)
        """,
        batch_params,
    )
    return len(result.segments)


def _create_concept_nodes(result: PipelineResult) -> int:
    """Create Concept nodes and EXPLAINED_IN edges to Segments. Returns count."""
    # Build mapping: concept_name -> list of segment_ids where it appears
    concept_segments: dict[str, list[str]] = {}
    for ku in result.knowledge_units:
        for concept in ku.concepts:
            concept_segments.setdefault(concept.name, [])
            if ku.segment_id not in concept_segments[concept.name]:
                concept_segments[concept.name].append(ku.segment_id)

    # Batch create concept nodes
    concept_params = [
        {
            "name": concept.name,
            "aliases": concept.aliases,
            "type": concept.type,
            "definition": concept.definition,
            "importance": concept.importance,
        }
        for concept in result.unique_concepts
    ]
    run_write_batch(
        """
        MERGE (c:Concept {name: $name})
        SET c.aliases = $aliases,
            c.type = $type,
            c.definition = $definition,
            c.importance = $importance
        """,
        concept_params,
    )

    # Batch create EXPLAINED_IN edges
    edge_params = [
        {
            "concept_name": concept.name,
            "segment_id": seg_id,
            "video_id": result.video_id,
        }
        for concept in result.unique_concepts
        for seg_id in concept_segments.get(concept.name, [])
    ]
    run_write_batch(
        """
        MATCH (c:Concept {name: $concept_name})
        MATCH (s:Segment {id: $segment_id})
        MERGE (c)-[:EXPLAINED_IN {video_id: $video_id}]->(s)
        """,
        edge_params,
    )

    return len(result.unique_concepts)


def _create_relationships(result: PipelineResult) -> int:
    """Create Concept-to-Concept relationship edges. Returns count."""
    seen = set()
    count = 0

    for ku in result.knowledge_units:
        for rel in ku.relationships:
            rel_sig = (rel.from_concept, rel.to_concept, rel.type)
            if rel_sig in seen:
                continue
            seen.add(rel_sig)

            # Use APOC-free approach: dynamic rel type via separate queries per type
            rel_type = rel.type.upper()
            run_write(
                f"""
                MATCH (a:Concept {{name: $from_name}})
                MATCH (b:Concept {{name: $to_name}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r.evidence = $evidence,
                    r.video_id = $video_id
                """,
                {
                    "from_name": rel.from_concept,
                    "to_name": rel.to_concept,
                    "evidence": rel.evidence,
                    "video_id": result.video_id,
                },
            )
            count += 1

    return count


def _create_example_nodes(result: PipelineResult) -> int:
    """Create Example nodes with ILLUSTRATES edges to Concepts. Returns count."""
    example_params = []
    for ku in result.knowledge_units:
        for i, ex in enumerate(ku.examples):
            example_id = f"{ku.segment_id}_ex{i + 1:02d}"
            example_params.append({
                "id": example_id,
                "description": ex.description,
                "segment_id": ku.segment_id,
                "concept_name": ex.illustrates,
            })

    run_write_batch(
        """
        MERGE (e:Example {id: $id})
        SET e.description = $description,
            e.segment_id = $segment_id
        WITH e
        MATCH (c:Concept {name: $concept_name})
        MERGE (e)-[:ILLUSTRATES]->(c)
        """,
        example_params,
    )

    return len(example_params)


def build_graph(result: PipelineResult) -> dict:
    """Build the full knowledge graph in Neo4j from a PipelineResult.

    Returns:
        Dict with counts: {videos, segments, concepts, relationships, examples}
    """
    console.print(f"\n[bold blue]Building knowledge graph for:[/] {result.video_title}")

    ensure_constraints()

    videos = _create_video_node(result)
    console.print(f"  [dim]Video node created[/]")

    segments = _create_segment_nodes(result)
    console.print(f"  [dim]{segments} segment nodes created[/]")

    concepts = _create_concept_nodes(result)
    console.print(f"  [dim]{concepts} concept nodes created[/]")

    relationships = _create_relationships(result)
    console.print(f"  [dim]{relationships} relationship edges created[/]")

    examples = _create_example_nodes(result)
    console.print(f"  [dim]{examples} example nodes created[/]")

    stats = {
        "videos": videos,
        "segments": segments,
        "concepts": concepts,
        "relationships": relationships,
        "examples": examples,
    }

    console.print(f"[green]Graph built successfully:[/] {stats}")
    return stats


def build_graph_from_json(json_path: str) -> dict:
    """Load a PipelineResult JSON file and build the graph.

    Args:
        json_path: Path to the JSON file from Phase 1 pipeline output.

    Returns:
        Dict with node/edge counts.
    """
    path = Path(json_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    result = PipelineResult.model_validate(data)
    return build_graph(result)
