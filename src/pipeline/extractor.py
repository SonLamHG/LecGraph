"""Knowledge extraction from segments using LLM (OpenAI API)."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn

from src.config import settings
from src.pipeline.llm_utils import (
    QuotaExhaustedError,
    call_llm as _call_llm,
    parse_json_response as _parse_json_response,
)
from src.pipeline.models import (
    Concept,
    Example,
    KeyQuote,
    KnowledgeUnit,
    Relationship,
    Segment,
    TimestampRange,
)

console = Console(force_terminal=True)

PROMPTS_DIR = Path(__file__).parent.parent / "config" / "prompts"


def _load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8")


def _extract_concepts(segment: Segment, video_title: str) -> list[Concept]:
    """Extract concepts from a segment (1 LLM call)."""
    template = _load_prompt("concept_extraction")
    prompt = template.format(
        segment_title=segment.title,
        video_title=video_title,
        start_time=segment.start,
        end_time=segment.end,
        transcript=segment.transcript,
    )

    response = _call_llm(prompt)
    raw_concepts = _parse_json_response(response)

    concepts = []
    for c in raw_concepts:
        concepts.append(Concept(
            name=c["name"],
            aliases=c.get("aliases", []),
            type=c.get("type", "definition"),
            definition=c.get("definition", ""),
            importance=c.get("importance", "mentioned"),
            timestamp_range=TimestampRange(start=segment.start, end=segment.end),
        ))

    return concepts


def _extract_relationships(
    segment: Segment,
    concepts: list[Concept],
) -> list[Relationship]:
    """Extract relationships between concepts (1 LLM call)."""
    if not concepts:
        return []

    template = _load_prompt("relationship_extraction")
    concepts_json = json.dumps(
        [{"name": c.name, "type": c.type, "definition": c.definition} for c in concepts],
        ensure_ascii=False,
        indent=2,
    )
    prompt = template.format(
        segment_title=segment.title,
        concepts_json=concepts_json,
        transcript=segment.transcript,
    )

    response = _call_llm(prompt)
    raw_rels = _parse_json_response(response)

    relationships = []
    for r in raw_rels:
        relationships.append(Relationship(
            from_concept=r["from_concept"],
            to_concept=r["to_concept"],
            type=r.get("type", "depends_on"),
            evidence=r.get("evidence", ""),
        ))

    return relationships


def _extract_metadata(segment: Segment, video_title: str) -> dict:
    """Extract segment title, key quotes, and examples (1 LLM call)."""
    template = _load_prompt("segment_naming")
    prompt = template.format(
        video_title=video_title,
        start_time=segment.start,
        end_time=segment.end,
        transcript=segment.transcript,
    )

    response = _call_llm(prompt)
    return _parse_json_response(response)


def extract_knowledge(
    segment: Segment,
    video_id: str,
    video_title: str,
) -> KnowledgeUnit:
    """
    Extract complete knowledge from a single segment.
    3 LLM calls: metadata + concepts (parallel), then relationships.
    """
    # Phase 1: metadata and concepts in parallel (2 LLM calls)
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_meta = executor.submit(_extract_metadata, segment, video_title)
        future_concepts = executor.submit(_extract_concepts, segment, video_title)
        metadata = future_meta.result()
        concepts = future_concepts.result()

    segment.title = metadata.get("title", segment.title)

    # Phase 2: relationships (depends on concepts, 1 LLM call)
    relationships = _extract_relationships(segment, concepts)

    # Build examples
    examples = []
    for ex in metadata.get("examples", []):
        examples.append(Example(
            description=ex.get("description", ""),
            illustrates=ex.get("illustrates", ""),
            timestamp=None,
        ))

    # Build key quotes
    key_quotes = []
    for kq in metadata.get("key_quotes", []):
        key_quotes.append(KeyQuote(
            text=kq.get("text", ""),
            timestamp=None,
            relevance=kq.get("relevance", ""),
        ))

    return KnowledgeUnit(
        segment_id=segment.segment_id,
        video_id=video_id,
        title=segment.title,
        timestamp=TimestampRange(start=segment.start, end=segment.end),
        concepts=concepts,
        relationships=relationships,
        examples=examples,
        key_quotes=key_quotes,
    )


def extract_all(
    segments: list[Segment],
    video_id: str,
    video_title: str,
) -> list[KnowledgeUnit]:
    """
    Extract knowledge from all segments.

    Args:
        segments: List of Segment objects from the segmenter
        video_id: Video identifier
        video_title: Video title

    Returns:
        List of KnowledgeUnit objects
    """
    console.print(
        f"\n[bold blue]Extracting knowledge from {len(segments)} segments...[/]"
    )
    console.print(f"[dim]Using model: {settings.llm_model}[/]")
    console.print(f"[dim]LLM calls per segment: 3 (metadata + concepts || relationships)[/]")
    console.print(f"[dim]Parallel workers: {settings.llm_max_workers}[/]")

    results: list[KnowledgeUnit | None] = [None] * len(segments)
    quota_exhausted = threading.Event()

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting...", total=len(segments))

        def _process_segment(index: int, seg: Segment) -> tuple[int, KnowledgeUnit]:
            if quota_exhausted.is_set():
                raise QuotaExhaustedError("Cancelled")
            return index, extract_knowledge(seg, video_id, video_title)

        with ThreadPoolExecutor(max_workers=settings.llm_max_workers) as executor:
            futures = {
                executor.submit(_process_segment, i, seg): i
                for i, seg in enumerate(segments)
            }

            for future in as_completed(futures):
                idx = futures[future]
                seg = segments[idx]
                try:
                    _, ku = future.result()
                    results[idx] = ku

                    progress.update(
                        task,
                        advance=1,
                        description=f"[{seg.segment_id}] {len(ku.concepts)} concepts",
                    )
                    console.print(
                        f"  [dim]* {seg.segment_id} \"{ku.title}\":[/] "
                        f"{len(ku.concepts)} concepts, "
                        f"{len(ku.relationships)} relationships"
                    )

                except QuotaExhaustedError:
                    quota_exhausted.set()
                    for f in futures:
                        f.cancel()
                    done_count = sum(1 for r in results if r is not None)
                    console.print(
                        "\n[bold red]API quota exhausted. Stopping extraction.[/]"
                        "\n[yellow]Check billing at https://platform.openai.com/account/billing[/]"
                        f"\n[dim]Partial results: {done_count}/{len(segments)} segments processed[/]"
                    )
                    break

                except Exception as e:
                    console.print(f"  [red]Error on {seg.segment_id}: {e}[/]")
                    progress.update(task, advance=1)

    knowledge_units = [ku for ku in results if ku is not None]

    total_concepts = sum(len(ku.concepts) for ku in knowledge_units)
    total_rels = sum(len(ku.relationships) for ku in knowledge_units)
    console.print(
        f"\n[green]Per-segment extraction complete:[/] "
        f"{total_concepts} concepts, {total_rels} relationships "
        f"from {len(knowledge_units)}/{len(segments)} segments"
    )

    # Global relationship pass
    if knowledge_units and not quota_exhausted.is_set():
        try:
            global_rels = _extract_global_relationships(knowledge_units, video_title)
            if global_rels:
                global_ku = KnowledgeUnit(
                    segment_id="global",
                    video_id=video_id,
                    title="Global Relationships",
                    timestamp=TimestampRange(start=0, end=0),
                    concepts=[],
                    relationships=global_rels,
                    examples=[],
                    key_quotes=[],
                )
                knowledge_units.append(global_ku)
                console.print(
                    f"[green]Global pass:[/] {len(global_rels)} cross-segment relationships added"
                )
        except QuotaExhaustedError:
            console.print("[yellow]Skipped global pass (quota exhausted)[/]")
        except Exception as e:
            console.print(f"[yellow]Global pass failed: {e}[/]")

    return knowledge_units


def _extract_global_relationships(
    knowledge_units: list[KnowledgeUnit],
    video_title: str,
) -> list[Relationship]:
    """Extract cross-segment relationships from all concepts (1 LLM call).

    Takes all unique concepts from all KUs and asks the LLM to find
    structural/prerequisite relationships between them.
    """
    # Collect unique concepts
    seen = set()
    all_concepts = []
    for ku in knowledge_units:
        for c in ku.concepts:
            if c.name not in seen:
                seen.add(c.name)
                all_concepts.append({"name": c.name, "type": c.type, "definition": c.definition})

    if len(all_concepts) < 2:
        return []

    template = _load_prompt("global_relationship_extraction")
    prompt = template.format(
        video_title=video_title,
        concepts_json=json.dumps(all_concepts, ensure_ascii=False, indent=2),
    )

    console.print(
        f"\n[bold blue]Global relationship pass:[/] {len(all_concepts)} concepts"
    )

    response = _call_llm(prompt)
    raw_rels = _parse_json_response(response)

    relationships = []
    for r in raw_rels:
        relationships.append(Relationship(
            from_concept=r["from_concept"],
            to_concept=r["to_concept"],
            type=r.get("type", "depends_on"),
            evidence=r.get("evidence", ""),
        ))

    return relationships
