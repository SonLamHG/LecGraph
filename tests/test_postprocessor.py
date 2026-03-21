"""Tests for post-processing concept deduplication."""

import pytest

from src.pipeline.models import Concept, KnowledgeUnit, Relationship, TimestampRange
from src.pipeline.postprocessor import (
    _fix_relationship_direction,
    _normalize_name,
    _pick_best_definition,
    _pick_best_importance,
    build_unique_concepts,
    deduplicate_concepts,
)


def _make_ku(
    seg_id: str,
    concepts: list[Concept],
    relationships: list[Relationship] | None = None,
) -> KnowledgeUnit:
    return KnowledgeUnit(
        segment_id=seg_id,
        video_id="vid_test",
        title=f"Title {seg_id}",
        timestamp=TimestampRange(start=0, end=60),
        concepts=concepts,
        relationships=relationships or [],
        examples=[],
        key_quotes=[],
    )


def _make_concept(name: str, definition: str = "", importance: str = "mentioned", aliases: list[str] | None = None) -> Concept:
    return Concept(
        name=name,
        aliases=aliases or [],
        type="definition",
        definition=definition,
        importance=importance,
        timestamp_range=TimestampRange(start=0, end=60),
    )


class TestNormalizeName:
    def test_lowercase(self):
        assert _normalize_name("Neural Network") == "neural network"

    def test_strip_plural(self):
        assert _normalize_name("Neural Networks") == "neural network"

    def test_no_strip_short(self):
        assert _normalize_name("bus") == "bus"

    def test_no_strip_double_s(self):
        assert _normalize_name("loss") == "loss"

    def test_strip_es_plural(self):
        # "Biases" -> "bias" (not "biase")
        assert _normalize_name("Biases") == "bias"

    def test_strip_hyphen(self):
        assert _normalize_name("Matrix-Vector Product") == "matrix vector product"

    def test_hyphen_and_no_hyphen_match(self):
        assert _normalize_name("Matrix-Vector Product") == _normalize_name("Matrix Vector Product")


class TestPickBestDefinition:
    def test_picks_longest(self):
        defs = ["short", "a much longer definition here"]
        assert _pick_best_definition(defs) == "a much longer definition here"

    def test_skips_empty(self):
        defs = ["", "valid"]
        assert _pick_best_definition(defs) == "valid"


class TestPickBestImportance:
    def test_core_wins(self):
        assert _pick_best_importance(["mentioned", "core", "supporting"]) == "core"

    def test_supporting_over_mentioned(self):
        assert _pick_best_importance(["mentioned", "supporting"]) == "supporting"


class TestFixRelationshipDirection:
    def test_correct_direction_unchanged(self):
        rel = Relationship(from_concept="Neuron", to_concept="Neural Network", type="is_part_of", evidence="")
        fixed = _fix_relationship_direction(rel)
        assert fixed.from_concept == "Neuron"
        assert fixed.to_concept == "Neural Network"

    def test_reversed_nn_neuron_swapped(self):
        # Neural Network contains "Neuron" stem -> swap
        rel = Relationship(from_concept="Neural Network", to_concept="Neuron", type="is_part_of", evidence="")
        fixed = _fix_relationship_direction(rel)
        assert fixed.from_concept == "Neuron"
        assert fixed.to_concept == "Neural Network"

    def test_ambiguous_names_unchanged(self):
        # "Input Layer" vs "Neuron" — no stem overlap, heuristic can't determine direction
        rel = Relationship(from_concept="Input Layer", to_concept="Neuron", type="is_part_of", evidence="")
        fixed = _fix_relationship_direction(rel)
        assert fixed.from_concept == "Input Layer"
        assert fixed.to_concept == "Neuron"

    def test_non_is_part_of_unchanged(self):
        rel = Relationship(from_concept="Neural Network", to_concept="Neuron", type="depends_on", evidence="")
        fixed = _fix_relationship_direction(rel)
        assert fixed.from_concept == "Neural Network"

    def test_weighted_sum_bias_not_swapped(self):
        # "Weighted Sum" does NOT contain "Bias" -> no swap
        rel = Relationship(from_concept="Weighted Sum", to_concept="Bias", type="is_part_of", evidence="")
        fixed = _fix_relationship_direction(rel)
        # These are unrelated names, no stem match -> keep as-is
        assert fixed.from_concept == "Weighted Sum"


class TestDeduplicateConcepts:
    def test_exact_name_dedup(self):
        kus = [
            _make_ku("seg1", [_make_concept("Neural Network", "def1")]),
            _make_ku("seg2", [_make_concept("Neural Network", "def2 longer definition")]),
        ]
        result = deduplicate_concepts(kus)
        assert len(result[0].concepts) == 1
        assert len(result[1].concepts) == 1
        assert result[0].concepts[0].definition == "def2 longer definition"
        assert result[1].concepts[0].definition == "def2 longer definition"

    def test_case_insensitive(self):
        kus = [
            _make_ku("seg1", [_make_concept("neural network", "short")]),
            _make_ku("seg2", [_make_concept("Neural Network", "a longer definition")]),
        ]
        result = deduplicate_concepts(kus)
        assert result[0].concepts[0].name == result[1].concepts[0].name

    def test_plural_match(self):
        kus = [
            _make_ku("seg1", [_make_concept("Neural Networks", "plural def")]),
            _make_ku("seg2", [_make_concept("Neural Network", "singular def here")]),
        ]
        result = deduplicate_concepts(kus)
        assert result[0].concepts[0].name == result[1].concepts[0].name

    def test_es_plural_match(self):
        kus = [
            _make_ku("seg1", [_make_concept("Bias", "short")]),
            _make_ku("seg2", [_make_concept("Biases", "longer bias definition")]),
        ]
        result = deduplicate_concepts(kus)
        assert result[0].concepts[0].name == result[1].concepts[0].name

    def test_hyphen_match(self):
        kus = [
            _make_ku("seg1", [_make_concept("Matrix Vector Product", "no hyphen")]),
            _make_ku("seg2", [_make_concept("Matrix-Vector Product", "with hyphen def")]),
        ]
        result = deduplicate_concepts(kus)
        assert result[0].concepts[0].name == result[1].concepts[0].name

    def test_alias_match(self):
        kus = [
            _make_ku("seg1", [_make_concept("Rectified Linear Unit", "full", aliases=["ReLU"])]),
            _make_ku("seg2", [_make_concept("ReLU", "short name version")]),
        ]
        result = deduplicate_concepts(kus)
        assert result[0].concepts[0].name == result[1].concepts[0].name

    def test_best_definition_kept(self):
        kus = [
            _make_ku("seg1", [_make_concept("Sigmoid", "short")]),
            _make_ku("seg2", [_make_concept("Sigmoid", "a detailed definition of sigmoid function")]),
        ]
        result = deduplicate_concepts(kus)
        assert "detailed" in result[0].concepts[0].definition

    def test_highest_importance_in_canonical(self):
        kus = [
            _make_ku("seg1", [_make_concept("Bias", importance="mentioned")]),
            _make_ku("seg2", [_make_concept("Bias", importance="core")]),
        ]
        result = deduplicate_concepts(kus)
        assert result[0].concepts[0].importance == "mentioned"
        assert result[1].concepts[0].importance == "core"

    def test_relationship_refs_updated(self):
        kus = [
            _make_ku(
                "seg1",
                [_make_concept("Neural Networks")],
                [Relationship(from_concept="Neural Networks", to_concept="Sigmoid", type="depends_on", evidence="test")],
            ),
        ]
        result = deduplicate_concepts(kus)
        rel = result[0].relationships[0]
        assert rel.from_concept == "Neural Networks"

    def test_duplicate_rels_removed(self):
        kus = [
            _make_ku(
                "seg1",
                [_make_concept("A"), _make_concept("B")],
                [
                    Relationship(from_concept="A", to_concept="B", type="depends_on", evidence="e1"),
                    Relationship(from_concept="A", to_concept="B", type="depends_on", evidence="e2"),
                ],
            ),
        ]
        result = deduplicate_concepts(kus)
        assert len(result[0].relationships) == 1

    def test_no_dup_within_single_ku(self):
        kus = [
            _make_ku("seg1", [
                _make_concept("Neural Network", "def1"),
                _make_concept("Neural Networks", "def2 longer"),
            ]),
        ]
        result = deduplicate_concepts(kus)
        assert len(result[0].concepts) == 1

    def test_is_part_of_direction_fixed(self):
        kus = [
            _make_ku(
                "seg1",
                [_make_concept("Neural Network"), _make_concept("Neuron")],
                [Relationship(from_concept="Neural Network", to_concept="Neuron", type="is_part_of", evidence="test")],
            ),
        ]
        result = deduplicate_concepts(kus)
        rel = result[0].relationships[0]
        assert rel.from_concept == "Neuron"
        assert rel.to_concept == "Neural Network"


class TestBuildUniqueConcepts:
    def test_deduplicates_across_kus(self):
        kus = [
            _make_ku("seg1", [_make_concept("Neural Network", "short", importance="mentioned")]),
            _make_ku("seg2", [_make_concept("Neural Network", "longer definition", importance="core")]),
            _make_ku("seg3", [_make_concept("Sigmoid", "sig def", importance="supporting")]),
        ]
        result = build_unique_concepts(kus)
        assert len(result) == 2
        nn = next(c for c in result if c.name == "Neural Network")
        assert nn.definition == "longer definition"
        assert nn.importance == "core"

    def test_sorted_by_importance(self):
        kus = [
            _make_ku("seg1", [
                _make_concept("A", importance="mentioned"),
                _make_concept("B", importance="core"),
                _make_concept("C", importance="supporting"),
            ]),
        ]
        result = build_unique_concepts(kus)
        assert result[0].name == "B"  # core first
        assert result[1].name == "C"  # supporting
        assert result[2].name == "A"  # mentioned
