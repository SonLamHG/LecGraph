"""Post-processing: deduplicate concepts and normalize relationships across knowledge units."""

import re

from src.pipeline.models import Concept, KnowledgeUnit, Relationship


IMPORTANCE_RANK = {"core": 3, "supporting": 2, "mentioned": 1}

# Relationship types where direction matters: from is the PART/SMALL, to is the WHOLE/BIG
_DIRECTIONAL_TYPES = {"is_part_of", "depends_on", "applies_to", "extends", "hyperparameter_of"}

# Valid concept types and aliases for normalization
VALID_TYPES = {
    "definition", "algorithm", "theorem", "technique", "property",
    "model", "framework", "function", "process", "structure", "metric",
}

TYPE_ALIASES = {
    "concept": "definition",
    "application": "technique",
    "method": "technique",
    "formula": "theorem",
    "equation": "theorem",
    "architecture": "model",
    "component": "structure",
    "layer": "structure",
    "measure": "metric",
    "loss": "function",
    "activation": "function",
}

# Noise keywords — concepts containing these are likely non-educational
_NOISE_KEYWORDS = {
    "patreon", "sponsor", "subscribe", "community support", "crowdfunding",
    "merchandise", "donation", "channel", "playlist", "click here",
    "like and subscribe", "notification bell",
}


def _normalize_name(name: str) -> str:
    """Normalize a concept name for matching.

    - lowercase
    - strip hyphens/underscores (Matrix-Vector → matrix vector)
    - handle plurals: 'es' suffix (biases → bias), 's' suffix (networks → network)
    """
    name = name.strip().lower()
    # Replace hyphens and underscores with spaces
    name = re.sub(r"[-_]", " ", name)
    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name).strip()
    # Handle 'ies' -> 'y' (e.g. boundaries -> boundary)
    if name.endswith("ies") and len(name) > 4:
        name = name[:-3] + "y"
    # Handle 'ses', 'xes', 'zes', 'ches', 'shes' -> strip 'es'
    elif re.search(r"(s|x|z|ch|sh)es$", name) and len(name) > 4:
        name = name[:-2]
    # Handle 'es' for other words (e.g. "atoes" -> "potato" won't match, but keep simple)
    elif name.endswith("es") and len(name) > 4:
        name = name[:-2]
    # Handle simple 's' plural (but not words ending in vowel+s like "bias", "campus")
    elif (name.endswith("s") and len(name) > 3
          and not name.endswith("ss")
          and name[-2] not in "aeiou"):
        name = name[:-1]
    return name


def _pick_best_definition(definitions: list[str]) -> str:
    """Pick the longest non-trivial definition (< 500 chars)."""
    candidates = [d for d in definitions if d and len(d) < 500]
    if not candidates:
        return definitions[0] if definitions else ""
    return max(candidates, key=len)


def _pick_best_importance(importances: list[str]) -> str:
    """Pick the highest importance level."""
    return max(importances, key=lambda x: IMPORTANCE_RANK.get(x, 0))


def _fix_relationship_direction(rel: Relationship) -> Relationship:
    """Fix reversed is_part_of relationships using heuristics.

    Rules for is_part_of (from=PART, to=WHOLE):
    - The WHOLE typically has a shorter or more general name
    - If from_concept contains to_concept as substring, they're likely reversed
      (e.g. "Neural Network" --[is_part_of]--> "Neuron" is wrong because
       "Neural Network" contains "Neuron")
    """
    if rel.type != "is_part_of":
        return rel

    from_lower = rel.from_concept.lower()
    to_lower = rel.to_concept.lower()

    should_swap = False

    # Rule 1: If from contains to as a word/substring, from is likely the WHOLE
    # e.g. "Neural Network" contains "Neuron" → swap
    # But "Input Layer" does NOT contain "Neural Network"
    to_words = set(to_lower.split())
    from_words = set(from_lower.split())

    # Check if to_concept's root words are a subset of from_concept
    # "Neuron" words = {"neuron"}, "Neural Network" words = {"neural", "network"}
    # We check if any to_word is a stem-prefix of any from_word
    for tw in to_words:
        for fw in from_words:
            # "neuron" is prefix of "neural"? No. But check stem match
            if fw.startswith(tw[:4]) or tw.startswith(fw[:4]):
                if len(from_lower) > len(to_lower):
                    should_swap = True
                    break
        if should_swap:
            break

    # Rule 2: Specific known patterns where the bigger concept should be "to"
    # If from is clearly a compound/larger concept containing to
    if to_lower in from_lower:
        should_swap = True

    if should_swap:
        return Relationship(
            from_concept=rel.to_concept,
            to_concept=rel.from_concept,
            type=rel.type,
            evidence=rel.evidence,
        )

    return rel


def filter_noise_concepts(knowledge_units: list[KnowledgeUnit]) -> list[KnowledgeUnit]:
    """Remove non-educational noise concepts (sponsors, promotions, etc.)."""
    def _is_noise(concept: Concept) -> bool:
        name_lower = concept.name.lower()
        def_lower = concept.definition.lower()
        text = name_lower + " " + def_lower

        # Check noise keywords
        for keyword in _NOISE_KEYWORDS:
            if keyword in text:
                return True

        return False

    filtered_count = 0
    for ku in knowledge_units:
        noise_names = {c.name for c in ku.concepts if _is_noise(c)}
        if noise_names:
            filtered_count += len(noise_names)
            ku.concepts = [c for c in ku.concepts if c.name not in noise_names]
            ku.relationships = [
                r for r in ku.relationships
                if r.from_concept not in noise_names and r.to_concept not in noise_names
            ]

    return knowledge_units


def normalize_concept_types(knowledge_units: list[KnowledgeUnit]) -> list[KnowledgeUnit]:
    """Normalize concept types to the valid set."""
    for ku in knowledge_units:
        for concept in ku.concepts:
            t = concept.type.lower().strip()
            if t in VALID_TYPES:
                concept.type = t
            elif t in TYPE_ALIASES:
                concept.type = TYPE_ALIASES[t]
            else:
                concept.type = "definition"
    return knowledge_units


def deduplicate_concepts(knowledge_units: list[KnowledgeUnit]) -> list[KnowledgeUnit]:
    """Deduplicate concepts across all knowledge units.

    1. Build a canonical registry keyed by normalized name.
    2. Merge definitions, aliases, importance across occurrences.
    3. Rebuild each KU with deduplicated concepts and normalized relationships.
    4. Fix relationship directions.
    """
    # Phase 1: Build registry
    registry: dict[str, dict] = {}

    for ku in knowledge_units:
        for concept in ku.concepts:
            key = _normalize_name(concept.name)
            alias_keys = {_normalize_name(a) for a in concept.aliases}

            # Find existing entry by name or alias
            matched_key = None
            if key in registry:
                matched_key = key
            else:
                for ak in alias_keys:
                    if ak in registry:
                        matched_key = ak
                        break
                if matched_key is None:
                    for rk, rv in registry.items():
                        if key in rv["alias_keys"] or alias_keys & rv["alias_keys"]:
                            matched_key = rk
                            break

            if matched_key is not None:
                entry = registry[matched_key]
                entry["definitions"].append(concept.definition)
                entry["importances"].append(concept.importance)
                entry["aliases"].update(concept.aliases)
                entry["aliases"].add(concept.name)
                entry["alias_keys"].update(alias_keys)
                entry["alias_keys"].add(key)
            else:
                registry[key] = {
                    "canonical_name": concept.name,
                    "definitions": [concept.definition],
                    "importances": [concept.importance],
                    "type": concept.type,
                    "aliases": set(concept.aliases) | {concept.name},
                    "alias_keys": alias_keys | {key},
                }

    # Phase 2: Build canonical concepts and name lookup
    canonical: dict[str, Concept] = {}
    name_to_canonical: dict[str, str] = {}

    for key, entry in registry.items():
        cname = entry["canonical_name"]
        best_def = _pick_best_definition(entry["definitions"])
        best_imp = _pick_best_importance(entry["importances"])
        aliases = sorted(entry["aliases"] - {cname})

        canonical[key] = Concept(
            name=cname,
            aliases=aliases,
            type=entry["type"],
            definition=best_def,
            importance=best_imp,
            timestamp_range=None,
        )

        for alias in entry["aliases"]:
            name_to_canonical[_normalize_name(alias)] = cname
        name_to_canonical[key] = cname

    # Phase 3: Rebuild knowledge units
    for ku in knowledge_units:
        seen = set()
        new_concepts = []
        for concept in ku.concepts:
            key = _normalize_name(concept.name)
            cname = name_to_canonical.get(key, concept.name)
            if cname not in seen:
                seen.add(cname)
                # Look up canonical by the normalized canonical name
                canon_key = _normalize_name(cname)
                canon = canonical.get(canon_key)
                if canon:
                    new_concepts.append(Concept(
                        name=canon.name,
                        aliases=canon.aliases,
                        type=canon.type,
                        definition=canon.definition,
                        importance=concept.importance,
                        timestamp_range=concept.timestamp_range,
                    ))
                else:
                    new_concepts.append(concept)
        ku.concepts = new_concepts

        # Phase 4: Normalize, fix direction, and dedup relationships
        seen_rels = set()
        new_rels = []
        for rel in ku.relationships:
            from_name = name_to_canonical.get(_normalize_name(rel.from_concept), rel.from_concept)
            to_name = name_to_canonical.get(_normalize_name(rel.to_concept), rel.to_concept)
            fixed_rel = _fix_relationship_direction(Relationship(
                from_concept=from_name,
                to_concept=to_name,
                type=rel.type,
                evidence=rel.evidence,
            ))
            rel_sig = (fixed_rel.from_concept, fixed_rel.to_concept, fixed_rel.type)
            if rel_sig not in seen_rels:
                seen_rels.add(rel_sig)
                new_rels.append(fixed_rel)
        ku.relationships = new_rels

    return knowledge_units


def build_unique_concepts(knowledge_units: list[KnowledgeUnit]) -> list[Concept]:
    """Build a list of unique concepts across all knowledge units.

    Returns one Concept per unique name with best definition,
    highest importance, and merged aliases.
    """
    registry: dict[str, dict] = {}

    for ku in knowledge_units:
        for concept in ku.concepts:
            name = concept.name
            if name in registry:
                entry = registry[name]
                entry["definitions"].append(concept.definition)
                entry["importances"].append(concept.importance)
                entry["aliases"].update(concept.aliases)
                if concept.timestamp_range:
                    entry["timestamps"].append(concept.timestamp_range)
                entry["segment_count"] += 1
            else:
                registry[name] = {
                    "type": concept.type,
                    "definitions": [concept.definition],
                    "importances": [concept.importance],
                    "aliases": set(concept.aliases),
                    "timestamps": [concept.timestamp_range] if concept.timestamp_range else [],
                    "segment_count": 1,
                }

    result = []
    for name, entry in registry.items():
        result.append(Concept(
            name=name,
            aliases=sorted(entry["aliases"] - {name}),
            type=entry["type"],
            definition=_pick_best_definition(entry["definitions"]),
            importance=_pick_best_importance(entry["importances"]),
            timestamp_range=entry["timestamps"][0] if entry["timestamps"] else None,
        ))

    # Sort: core first, then supporting, then mentioned; within same importance, alphabetical
    result.sort(key=lambda c: (-IMPORTANCE_RANK.get(c.importance, 0), c.name))
    return result
