"""Learning path generation using topological sort on prerequisite graph."""

from collections import defaultdict, deque

from pydantic import BaseModel
from rich.console import Console

from src.db.neo4j_client import run_query

console = Console(force_terminal=True)


class LearningStep(BaseModel):
    """A single step in a learning path."""
    concept: str
    definition: str
    video_id: str | None = None
    video_title: str | None = None
    segment_id: str | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    estimated_duration: float = 0.0  # seconds


class LearningPath(BaseModel):
    """Complete learning path for a target concept."""
    target_concept: str
    steps: list[LearningStep]
    estimated_total_time: float  # seconds
    known_concepts_skipped: list[str] = []


def _build_dependency_graph(concept_name: str, max_depth: int = 10) -> tuple[
    dict[str, list[str]],  # adjacency: concept -> list of prereqs
    dict[str, dict],       # concept_info: concept -> {definition, video_id, ...}
]:
    """Build a dependency graph from Neo4j for topological sorting.

    Returns adjacency list (concept -> dependencies) and concept metadata.
    """
    query = f"""
    MATCH path = (target:Concept {{name: $name}})-[:DEPENDS_ON*0..{max_depth}]->(prereq:Concept)
    WITH prereq, min(length(path)) AS depth
    OPTIONAL MATCH (prereq)-[:EXPLAINED_IN]->(s:Segment)-[:BELONGS_TO]->(v:Video)
    RETURN prereq.name AS name,
           prereq.definition AS definition,
           v.id AS video_id,
           v.title AS video_title,
           s.id AS segment_id,
           s.start AS timestamp_start,
           s.end AS timestamp_end,
           depth
    ORDER BY depth ASC
    """

    rows = run_query(query, {"name": concept_name})

    # Build concept info (first appearance wins for segment)
    concept_info: dict[str, dict] = {}
    for row in rows:
        name = row["name"]
        if name not in concept_info:
            concept_info[name] = {
                "definition": row.get("definition", ""),
                "video_id": row.get("video_id"),
                "video_title": row.get("video_title"),
                "segment_id": row.get("segment_id"),
                "timestamp_start": row.get("timestamp_start"),
                "timestamp_end": row.get("timestamp_end"),
            }

    # Get direct DEPENDS_ON edges between all concepts in the subgraph
    if not concept_info:
        return {}, {}

    names = list(concept_info.keys())
    edge_query = """
    MATCH (a:Concept)-[:DEPENDS_ON]->(b:Concept)
    WHERE a.name IN $names AND b.name IN $names
    RETURN a.name AS from_concept, b.name AS to_concept
    """
    edge_rows = run_query(edge_query, {"names": names})

    # adjacency: concept -> list of its prerequisites (what it depends on)
    adjacency: dict[str, list[str]] = defaultdict(list)
    for row in edge_rows:
        adjacency[row["from_concept"]].append(row["to_concept"])

    return dict(adjacency), concept_info


def _topological_sort(
    adjacency: dict[str, list[str]],
    all_nodes: set[str],
) -> list[str]:
    """Topological sort using Kahn's algorithm (BFS with in-degree tracking).

    Returns concepts in learning order (prerequisites first).
    """
    # Compute in-degree
    in_degree: dict[str, int] = {node: 0 for node in all_nodes}
    for node, deps in adjacency.items():
        for dep in deps:
            if dep in in_degree:
                # dep is depended upon by node, so in topological order dep comes before node
                pass

    # Reverse adjacency: if A depends_on B, then B must come before A
    # So we need: edge from B -> A in topological graph
    reverse_adj: dict[str, list[str]] = defaultdict(list)
    for node, deps in adjacency.items():
        for dep in deps:
            if dep in all_nodes:
                reverse_adj[dep].append(node)
                in_degree[node] = in_degree.get(node, 0) + 1

    # Reset in-degrees properly
    in_degree = {node: 0 for node in all_nodes}
    for node, successors in reverse_adj.items():
        for succ in successors:
            in_degree[succ] += 1

    # BFS from nodes with in-degree 0
    queue = deque(node for node in all_nodes if in_degree[node] == 0)
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for succ in reverse_adj.get(node, []):
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)

    # If there are remaining nodes (cycle), append them at the end
    remaining = all_nodes - set(result)
    result.extend(sorted(remaining))

    return result


def generate_learning_path(
    target_concept: str,
    known_concepts: list[str] | None = None,
    max_depth: int = 10,
) -> LearningPath:
    """Generate a learning path for a target concept.

    Args:
        target_concept: The concept the user wants to learn.
        known_concepts: Concepts the user already knows (will be skipped).
        max_depth: Maximum prerequisite depth.

    Returns:
        LearningPath with ordered steps.
    """
    known = set(known_concepts or [])
    console.print(f"\n[bold blue]Generating learning path for:[/] {target_concept}")
    if known:
        console.print(f"  [dim]Known concepts: {', '.join(known)}[/]")

    adjacency, concept_info = _build_dependency_graph(target_concept, max_depth)

    if not concept_info:
        return LearningPath(
            target_concept=target_concept,
            steps=[],
            estimated_total_time=0.0,
            known_concepts_skipped=[],
        )

    # Remove known concepts
    all_nodes = set(concept_info.keys()) - known
    # Also remove edges to/from known concepts
    filtered_adj: dict[str, list[str]] = {}
    for node, deps in adjacency.items():
        if node in all_nodes:
            filtered_adj[node] = [d for d in deps if d in all_nodes]

    # Topological sort
    order = _topological_sort(filtered_adj, all_nodes)

    # Build learning steps
    steps = []
    total_time = 0.0
    for concept_name in order:
        info = concept_info.get(concept_name, {})
        start = info.get("timestamp_start")
        end = info.get("timestamp_end")
        duration = (end - start) if start is not None and end is not None else 0.0

        steps.append(LearningStep(
            concept=concept_name,
            definition=info.get("definition", ""),
            video_id=info.get("video_id"),
            video_title=info.get("video_title"),
            segment_id=info.get("segment_id"),
            timestamp_start=start,
            timestamp_end=end,
            estimated_duration=duration,
        ))
        total_time += duration

    skipped = sorted(known & set(concept_info.keys()))

    result = LearningPath(
        target_concept=target_concept,
        steps=steps,
        estimated_total_time=total_time,
        known_concepts_skipped=skipped,
    )

    console.print(
        f"[green]Learning path:[/] {len(steps)} steps, "
        f"est. {total_time / 60:.0f} min"
    )
    return result
