"""Prerequisite query: find all prerequisites of a concept via graph traversal."""

from pydantic import BaseModel
from rich.console import Console

from src.db.neo4j_client import run_query

console = Console(force_terminal=True)


class PrerequisiteNode(BaseModel):
    """A single prerequisite concept."""
    name: str
    definition: str
    depth: int
    video_id: str | None = None
    segment_id: str | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None


class PrerequisiteResult(BaseModel):
    """Complete prerequisite chain for a concept."""
    concept: str
    prerequisites: list[PrerequisiteNode]
    max_depth: int


def get_prerequisites(concept_name: str, max_depth: int = 10) -> PrerequisiteResult:
    """Get all prerequisites of a concept by traversing DEPENDS_ON edges.

    Args:
        concept_name: Name of the target concept.
        max_depth: Maximum traversal depth.

    Returns:
        PrerequisiteResult with ordered prerequisites (shallowest first).
    """
    console.print(f"\n[bold blue]Prerequisites for:[/] {concept_name}")

    # Neo4j variable-length path — max_depth is a controlled integer, safe to format
    query = f"""
    MATCH path = (target:Concept {{name: $name}})-[:DEPENDS_ON*1..{max_depth}]->(prereq:Concept)
    WITH prereq, min(length(path)) AS depth
    OPTIONAL MATCH (prereq)-[:EXPLAINED_IN]->(s:Segment)-[:BELONGS_TO]->(v:Video)
    RETURN prereq.name AS name,
           prereq.definition AS definition,
           depth,
           v.id AS video_id,
           s.id AS segment_id,
           s.start AS timestamp_start,
           s.end AS timestamp_end
    ORDER BY depth ASC
    """

    rows = run_query(query, {"name": concept_name})

    # Deduplicate (a prereq may have multiple segment appearances)
    seen = set()
    prerequisites = []
    for row in rows:
        name = row["name"]
        if name not in seen:
            seen.add(name)
            prerequisites.append(PrerequisiteNode(
                name=name,
                definition=row.get("definition", ""),
                depth=row["depth"],
                video_id=row.get("video_id"),
                segment_id=row.get("segment_id"),
                timestamp_start=row.get("timestamp_start"),
                timestamp_end=row.get("timestamp_end"),
            ))

    result = PrerequisiteResult(
        concept=concept_name,
        prerequisites=prerequisites,
        max_depth=max(p.depth for p in prerequisites) if prerequisites else 0,
    )

    console.print(f"[green]Found {len(prerequisites)} prerequisites[/]")
    return result
