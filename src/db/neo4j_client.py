"""Neo4j database client with thread-safe singleton driver."""

import threading

from neo4j import GraphDatabase
from rich.console import Console

from src.config import settings

console = Console(force_terminal=True)

_driver = None
_driver_lock = threading.Lock()


def get_driver():
    """Get or create the Neo4j driver instance (thread-safe)."""
    global _driver
    if _driver is None:
        with _driver_lock:
            if _driver is None:
                _driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
    return _driver


def close_driver():
    """Close the Neo4j driver."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def run_query(cypher: str, params: dict | None = None) -> list[dict]:
    """Execute a Cypher query and return results as list of dicts."""
    driver = get_driver()
    with driver.session(database=settings.neo4j_database) as session:
        result = session.run(cypher, params or {})
        return [record.data() for record in result]


def run_write(cypher: str, params: dict | None = None) -> None:
    """Execute a write Cypher query."""
    driver = get_driver()
    with driver.session(database=settings.neo4j_database) as session:
        session.run(cypher, params or {})


def run_write_batch(cypher: str, batch_params: list[dict]) -> None:
    """Execute a write Cypher query for each param set in a single transaction.

    Much faster than individual run_write calls — avoids per-query transaction overhead.
    """
    if not batch_params:
        return
    driver = get_driver()
    with driver.session(database=settings.neo4j_database) as session:
        with session.begin_transaction() as tx:
            for params in batch_params:
                tx.run(cypher, params)
            tx.commit()


def ensure_constraints():
    """Create uniqueness constraints and indexes if they don't exist."""
    constraints = [
        "CREATE CONSTRAINT concept_name IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT segment_id IF NOT EXISTS FOR (s:Segment) REQUIRE s.id IS UNIQUE",
        "CREATE CONSTRAINT video_id IF NOT EXISTS FOR (v:Video) REQUIRE v.id IS UNIQUE",
    ]
    indexes = [
        "CREATE INDEX concept_type_idx IF NOT EXISTS FOR (c:Concept) ON (c.type)",
        "CREATE INDEX concept_importance_idx IF NOT EXISTS FOR (c:Concept) ON (c.importance)",
        # Composite indexes for common query patterns
        "CREATE INDEX segment_video_idx IF NOT EXISTS FOR (s:Segment) ON (s.video_id)",
        "CREATE INDEX example_segment_idx IF NOT EXISTS FOR (e:Example) ON (e.segment_id)",
    ]

    driver = get_driver()
    with driver.session(database=settings.neo4j_database) as session:
        for stmt in constraints + indexes:
            session.run(stmt)

    console.print("[green]Neo4j constraints and indexes ensured.[/]")
