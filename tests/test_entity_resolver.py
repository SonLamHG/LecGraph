"""Tests for entity_resolver module."""

from unittest.mock import patch

import pytest

from src.pipeline.entity_resolver import _apply_merges, _find_candidates, resolve_entities
from src.pipeline.models import Concept


def _make_concepts() -> list[Concept]:
    return [
        Concept(
            name="Artificial Intelligence",
            aliases=["AI"],
            type="definition",
            definition="The field of making intelligent machines.",
            importance="core",
        ),
        Concept(
            name="AI",
            aliases=["Artificial Intelligence"],
            type="definition",
            definition="Intelligence exhibited by machines.",
            importance="supporting",
        ),
        Concept(
            name="Machine Learning",
            aliases=["ML"],
            type="definition",
            definition="A subset of AI that learns from data.",
            importance="core",
        ),
        Concept(
            name="Gradient Descent",
            aliases=["GD"],
            type="algorithm",
            definition="An optimization algorithm.",
            importance="supporting",
        ),
    ]


@patch("src.pipeline.entity_resolver.embed_texts")
def test_find_candidates_alias_overlap(mock_embed):
    """Concepts with overlapping aliases should be candidates."""
    concepts = _make_concepts()
    # Return dummy embeddings (4 concepts, 3 dims)
    # Make AI and Artificial Intelligence have similar embeddings
    mock_embed.return_value = [
        [0.9, 0.1, 0.0],  # Artificial Intelligence
        [0.85, 0.15, 0.0],  # AI
        [0.1, 0.9, 0.0],  # Machine Learning
        [0.0, 0.1, 0.9],  # Gradient Descent
    ]

    candidates = _find_candidates(concepts, threshold=0.75)

    # AI and Artificial Intelligence should be candidates (alias overlap)
    pair_indices = {(c[0], c[1]) for c in candidates}
    assert (0, 1) in pair_indices


@patch("src.pipeline.entity_resolver.embed_texts")
def test_find_candidates_high_similarity(mock_embed):
    """Concepts with high embedding similarity should be candidates."""
    concepts = _make_concepts()
    mock_embed.return_value = [
        [0.9, 0.1, 0.0],
        [0.88, 0.12, 0.0],  # Very similar to first
        [0.1, 0.9, 0.0],
        [0.0, 0.1, 0.9],
    ]

    candidates = _find_candidates(concepts, threshold=0.95)

    # Even with high threshold, alias overlap should catch (0,1)
    pair_indices = {(c[0], c[1]) for c in candidates}
    assert (0, 1) in pair_indices
    # ML and GD should NOT be candidates
    assert (2, 3) not in pair_indices


@patch("src.pipeline.entity_resolver.embed_texts")
def test_find_candidates_no_duplicates(mock_embed):
    """Completely different concepts should not be candidates."""
    concepts = [
        Concept(name="Physics", aliases=[], type="definition",
                definition="Study of matter.", importance="core"),
        Concept(name="Literature", aliases=[], type="definition",
                definition="Study of written works.", importance="core"),
    ]
    mock_embed.return_value = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],  # Orthogonal
    ]

    candidates = _find_candidates(concepts, threshold=0.75)
    assert len(candidates) == 0


def test_apply_merges_same():
    """SAME verdicts should merge concepts."""
    concepts = _make_concepts()
    verdicts = [
        {"index_a": 0, "index_b": 1, "verdict": "SAME", "reason": "Same concept"},
    ]

    merged = _apply_merges(concepts, verdicts)
    assert len(merged) == 3  # 4 -> 3 (AI and Artificial Intelligence merged)

    # Find the merged concept
    ai_concept = next(c for c in merged if c.name == "Artificial Intelligence")
    assert "AI" in ai_concept.aliases
    assert ai_concept.importance == "core"  # Highest importance


def test_apply_merges_different():
    """DIFFERENT verdicts should not merge."""
    concepts = _make_concepts()
    verdicts = [
        {"index_a": 0, "index_b": 2, "verdict": "DIFFERENT", "reason": "Distinct concepts"},
    ]

    merged = _apply_merges(concepts, verdicts)
    assert len(merged) == 4  # No change


def test_apply_merges_empty():
    """No verdicts should return all concepts."""
    concepts = _make_concepts()
    merged = _apply_merges(concepts, [])
    assert len(merged) == 4


def test_apply_merges_transitive():
    """If A=B and B=C, then A=B=C should all merge."""
    concepts = [
        Concept(name="A", aliases=[], type="definition",
                definition="Concept A.", importance="core"),
        Concept(name="B", aliases=[], type="definition",
                definition="Concept B description longer.", importance="supporting"),
        Concept(name="C", aliases=[], type="definition",
                definition="Concept C.", importance="mentioned"),
    ]
    verdicts = [
        {"index_a": 0, "index_b": 1, "verdict": "SAME", "reason": "A=B"},
        {"index_a": 1, "index_b": 2, "verdict": "SAME", "reason": "B=C"},
    ]

    merged = _apply_merges(concepts, verdicts)
    assert len(merged) == 1
    assert merged[0].name == "A"
    assert "B" in merged[0].aliases
    assert "C" in merged[0].aliases
    assert merged[0].importance == "core"


@patch("src.pipeline.entity_resolver._verify_candidates")
@patch("src.pipeline.entity_resolver._find_candidates")
def test_resolve_entities_full(mock_find, mock_verify):
    """Full resolve_entities pipeline."""
    concepts = _make_concepts()
    mock_find.return_value = [(0, 1, 0.95)]
    mock_verify.return_value = [
        {"index_a": 0, "index_b": 1, "verdict": "SAME", "reason": "Same concept"},
    ]

    resolved = resolve_entities(concepts)
    assert len(resolved) == 3


def test_resolve_entities_single_concept():
    """Single concept should be returned as-is."""
    concepts = [
        Concept(name="AI", aliases=[], type="definition",
                definition="Artificial Intelligence.", importance="core"),
    ]
    resolved = resolve_entities(concepts)
    assert len(resolved) == 1
    assert resolved[0].name == "AI"
