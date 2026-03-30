"""Entity resolution: merge duplicate concepts using embedding similarity + LLM verification."""

import json
from pathlib import Path

import numpy as np
from rich.console import Console

from src.config import settings
from src.pipeline.embeddings import embed_texts
from src.pipeline.llm_utils import call_llm, parse_json_response
from src.pipeline.models import Concept
from src.pipeline.postprocessor import (
    _normalize_name,
    _pick_best_definition,
    _pick_best_importance,
)

console = Console(force_terminal=True)

PROMPTS_DIR = Path(__file__).parent.parent / "config" / "prompts"


def _find_candidates(
    concepts: list[Concept],
    threshold: float | None = None,
) -> list[tuple[int, int, float]]:
    """Find candidate pairs of potentially duplicate concepts.

    Uses embedding similarity and alias overlap to identify pairs
    that might refer to the same concept.

    Returns:
        List of (index_a, index_b, similarity_score) tuples.
    """
    if len(concepts) < 2:
        return []

    if threshold is None:
        threshold = settings.entity_resolution_similarity_threshold

    # Embed all concept names
    names = [c.name for c in concepts]
    embeddings = np.array(embed_texts(names))

    # Compute pairwise cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-10)
    normalized = embeddings / norms
    sim_matrix = normalized @ normalized.T

    # Find pairs above threshold
    candidates = []
    for i in range(len(concepts)):
        for j in range(i + 1, len(concepts)):
            sim = float(sim_matrix[i, j])

            # Also check alias overlap
            aliases_i = {_normalize_name(a) for a in concepts[i].aliases} | {_normalize_name(concepts[i].name)}
            aliases_j = {_normalize_name(a) for a in concepts[j].aliases} | {_normalize_name(concepts[j].name)}
            alias_overlap = bool(aliases_i & aliases_j)

            if sim >= threshold or alias_overlap:
                candidates.append((i, j, sim))

    return candidates


def _verify_candidates(
    concepts: list[Concept],
    candidates: list[tuple[int, int, float]],
    batch_size: int = 10,
) -> list[dict]:
    """Verify candidate pairs using LLM.

    Args:
        concepts: Full list of concepts.
        candidates: List of (index_a, index_b, similarity) tuples.
        batch_size: Number of pairs per LLM call.

    Returns:
        List of dicts: {pair_index, index_a, index_b, verdict, reason}
    """
    if not candidates:
        return []

    template = (PROMPTS_DIR / "entity_resolution.txt").read_text(encoding="utf-8")
    all_verdicts = []

    for batch_start in range(0, len(candidates), batch_size):
        batch = candidates[batch_start:batch_start + batch_size]

        pairs_data = []
        for local_idx, (i, j, sim) in enumerate(batch):
            pairs_data.append({
                "pair_index": local_idx,
                "concept_a": {
                    "name": concepts[i].name,
                    "aliases": concepts[i].aliases,
                    "definition": concepts[i].definition,
                },
                "concept_b": {
                    "name": concepts[j].name,
                    "aliases": concepts[j].aliases,
                    "definition": concepts[j].definition,
                },
                "embedding_similarity": round(sim, 3),
            })

        prompt = template.format(pairs_json=json.dumps(pairs_data, ensure_ascii=False, indent=2))
        response = call_llm(prompt)
        verdicts = parse_json_response(response)

        for v in verdicts:
            local_idx = v["pair_index"]
            if 0 <= local_idx < len(batch):
                i, j, _ = batch[local_idx]
                all_verdicts.append({
                    "index_a": i,
                    "index_b": j,
                    "verdict": v["verdict"],
                    "reason": v.get("reason", ""),
                })

    return all_verdicts


def _apply_merges(
    concepts: list[Concept],
    verdicts: list[dict],
) -> list[Concept]:
    """Apply merge decisions to produce a deduplicated concept list.

    For SAME verdicts, merge the two concepts (combine aliases, pick best definition).
    """
    # Build union-find for SAME pairs
    parent = list(range(len(concepts)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[py] = px

    for v in verdicts:
        if v["verdict"] == "SAME":
            union(v["index_a"], v["index_b"])

    # Group concepts by their root
    groups: dict[int, list[int]] = {}
    for i in range(len(concepts)):
        root = find(i)
        groups.setdefault(root, []).append(i)

    # Merge each group into a single concept
    merged = []
    for indices in groups.values():
        group_concepts = [concepts[i] for i in indices]

        # Use the first concept's name as canonical
        canonical = group_concepts[0]
        all_aliases = set()
        all_definitions = []
        all_importances = []

        for c in group_concepts:
            all_aliases.update(c.aliases)
            all_aliases.add(c.name)
            all_definitions.append(c.definition)
            all_importances.append(c.importance)

        # Remove canonical name from aliases
        all_aliases.discard(canonical.name)

        merged.append(Concept(
            name=canonical.name,
            aliases=sorted(all_aliases),
            type=canonical.type,
            definition=_pick_best_definition(all_definitions),
            importance=_pick_best_importance(all_importances),
            timestamp_range=canonical.timestamp_range,
        ))

    return merged


def resolve_entities(
    concepts: list[Concept],
    threshold: float | None = None,
) -> list[Concept]:
    """Run full entity resolution pipeline on a list of concepts.

    1. Find candidate pairs by embedding similarity
    2. Verify candidates with LLM
    3. Merge confirmed duplicates

    Args:
        concepts: List of concepts (typically from build_unique_concepts).
        threshold: Similarity threshold override.

    Returns:
        Deduplicated list of concepts.
    """
    if len(concepts) < 2:
        return concepts

    console.print(f"\n[bold blue]Entity resolution:[/] {len(concepts)} concepts")

    candidates = _find_candidates(concepts, threshold)
    console.print(f"  [dim]{len(candidates)} candidate pairs found[/]")

    if not candidates:
        console.print("[green]No duplicates detected.[/]")
        return concepts

    verdicts = _verify_candidates(concepts, candidates)
    same_count = sum(1 for v in verdicts if v["verdict"] == "SAME")
    console.print(f"  [dim]LLM verified: {same_count} SAME, {len(verdicts) - same_count} not same[/]")

    merged = _apply_merges(concepts, verdicts)
    console.print(f"[green]Entity resolution complete:[/] {len(concepts)} -> {len(merged)} concepts")

    return merged
