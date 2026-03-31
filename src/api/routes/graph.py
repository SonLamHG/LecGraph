"""Graph exploration routes."""

from fastapi import APIRouter, HTTPException, Query

from src.api.models import ConceptDetailResponse, ConceptResponse
from src.db.neo4j_client import run_query
from src.search.prerequisites import get_prerequisites

router = APIRouter()


@router.get("/concepts", response_model=list[ConceptResponse])
async def list_concepts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List all concepts with pagination."""
    rows = run_query(
        """
        MATCH (c:Concept)
        RETURN c.name AS name, c.aliases AS aliases, c.type AS type,
               c.definition AS definition, c.importance AS importance
        ORDER BY c.importance DESC, c.name
        SKIP $skip LIMIT $limit
        """,
        {"skip": skip, "limit": limit},
    )
    return [
        ConceptResponse(
            name=r["name"],
            aliases=r.get("aliases") or [],
            type=r.get("type", ""),
            definition=r.get("definition", ""),
            importance=r.get("importance", ""),
        )
        for r in rows
    ]


@router.get("/data")
async def get_graph_data(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    """Get concepts + relationships in a single call for graph visualization.

    Avoids N+1 queries — returns all edges between the returned concepts.
    """
    # Get concepts
    concept_rows = run_query(
        """
        MATCH (c:Concept)
        RETURN c.name AS name, c.aliases AS aliases, c.type AS type,
               c.definition AS definition, c.importance AS importance
        ORDER BY c.importance DESC, c.name
        SKIP $skip LIMIT $limit
        """,
        {"skip": skip, "limit": limit},
    )
    concept_names = [r["name"] for r in concept_rows]

    # Get all relationships between these concepts in one query
    rel_rows = []
    if concept_names:
        rel_rows = run_query(
            """
            MATCH (a:Concept)-[r]->(b:Concept)
            WHERE a.name IN $names AND b.name IN $names
            RETURN a.name AS source, b.name AS target, type(r) AS type
            """,
            {"names": concept_names},
        )

    return {
        "concepts": [
            {
                "name": r["name"],
                "aliases": r.get("aliases") or [],
                "type": r.get("type", ""),
                "definition": r.get("definition", ""),
                "importance": r.get("importance", ""),
            }
            for r in concept_rows
        ],
        "relationships": [
            {"source": r["source"], "target": r["target"], "type": r["type"]}
            for r in rel_rows
        ],
    }


@router.get("/concepts/{name}", response_model=ConceptDetailResponse)
async def get_concept(name: str):
    """Get concept details with relationships and segments."""
    rows = run_query(
        "MATCH (c:Concept {name: $name}) RETURN c",
        {"name": name},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Concept '{name}' not found")

    c = rows[0]["c"]

    # Get relationships
    rel_rows = run_query(
        """
        MATCH (c:Concept {name: $name})-[r]->(other:Concept)
        RETURN type(r) AS rel_type, other.name AS target, r.evidence AS evidence
        UNION
        MATCH (other:Concept)-[r]->(c:Concept {name: $name})
        RETURN type(r) AS rel_type, other.name AS target, r.evidence AS evidence
        """,
        {"name": name},
    )

    # Get segments
    seg_rows = run_query(
        """
        MATCH (c:Concept {name: $name})-[:EXPLAINED_IN]->(s:Segment)-[:BELONGS_TO]->(v:Video)
        RETURN s.id AS segment_id, s.title AS title, v.id AS video_id,
               v.title AS video_title, s.start AS start, s.end AS end
        ORDER BY s.start
        """,
        {"name": name},
    )

    return ConceptDetailResponse(
        name=c.get("name", name),
        aliases=c.get("aliases") or [],
        type=c.get("type", ""),
        definition=c.get("definition", ""),
        importance=c.get("importance", ""),
        relationships=[
            {"type": r["rel_type"], "target": r["target"], "evidence": r.get("evidence", "")}
            for r in rel_rows
        ],
        segments=[
            {"segment_id": s["segment_id"], "title": s.get("title", ""),
             "video_id": s["video_id"], "video_title": s.get("video_title", ""),
             "start": s.get("start", 0.0), "end": s.get("end", 0.0)}
            for s in seg_rows
        ],
    )


@router.get("/concepts/{name}/prerequisites")
async def get_concept_prerequisites(name: str, max_depth: int = Query(10, ge=1, le=20)):
    """Get prerequisite chain for a concept."""
    result = get_prerequisites(name, max_depth)
    return result.model_dump()
