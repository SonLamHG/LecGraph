"""Knowledge extraction from segments using LLM (Claude API)."""

import json
from pathlib import Path

import anthropic
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn

from src.config import settings
from src.pipeline.models import (
    Concept,
    Example,
    KeyQuote,
    KnowledgeUnit,
    Relationship,
    Segment,
    TimestampRange,
)

console = Console()

PROMPTS_DIR = Path(__file__).parent.parent / "config" / "prompts"


def _load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8")


def _call_llm(prompt: str) -> str:
    """Call Claude API and return the response text."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _parse_json_response(text: str) -> list | dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    text = text.strip()

    # Strip markdown code block if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    return json.loads(text)


def _extract_concepts(segment: Segment, video_title: str) -> list[Concept]:
    """Pass 1: Extract concepts from a segment."""
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
    """Pass 2: Extract relationships between concepts."""
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
    """Extract segment title, key quotes, and examples."""
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
    Runs 3 LLM calls: metadata, concepts, relationships.
    """
    # Pass 0: Segment naming + examples + key quotes
    metadata = _extract_metadata(segment, video_title)
    segment.title = metadata.get("title", segment.title)

    # Pass 1: Concept extraction
    concepts = _extract_concepts(segment, video_title)

    # Pass 2: Relationship extraction
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
    console.print(f"[dim]LLM calls per segment: 3 (metadata + concepts + relationships)[/]")

    knowledge_units = []

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting...", total=len(segments))

        for seg in segments:
            try:
                ku = extract_knowledge(seg, video_id, video_title)
                knowledge_units.append(ku)

                concept_names = [c.name for c in ku.concepts]
                progress.update(
                    task,
                    advance=1,
                    description=f"[{seg.segment_id}] {len(ku.concepts)} concepts",
                )
                console.print(
                    f"  [dim]• {seg.segment_id} \"{ku.title}\":[/] "
                    f"{len(ku.concepts)} concepts, "
                    f"{len(ku.relationships)} relationships"
                )

            except Exception as e:
                console.print(f"  [red]Error processing {seg.segment_id}: {e}[/]")
                progress.update(task, advance=1)

    total_concepts = sum(len(ku.concepts) for ku in knowledge_units)
    total_rels = sum(len(ku.relationships) for ku in knowledge_units)
    console.print(
        f"\n[green]Extraction complete:[/] "
        f"{total_concepts} concepts, {total_rels} relationships "
        f"from {len(knowledge_units)} segments"
    )

    return knowledge_units
