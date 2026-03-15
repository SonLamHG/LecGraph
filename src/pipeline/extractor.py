"""Knowledge extraction from segments using LLM (Gemini API)."""

import json
import re
import time
from pathlib import Path

import google.generativeai as genai
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

console = Console(force_terminal=True)

PROMPTS_DIR = Path(__file__).parent.parent / "config" / "prompts"

_gemini_model = None


def _get_model():
    """Get or create the Gemini model instance."""
    global _gemini_model
    if _gemini_model is None:
        genai.configure(api_key=settings.gemini_api_key)
        _gemini_model = genai.GenerativeModel(settings.llm_model)
    return _gemini_model


def _load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8")


class QuotaExhaustedError(Exception):
    """Raised when the API key has no quota left (limit: 0). Retrying won't help."""
    pass


def _call_llm(prompt: str, max_retries: int = 3) -> str:
    """Call Gemini API with smart retry: only retry temporary rate limits."""
    model = _get_model()

    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=settings.llm_max_tokens,
                    temperature=0.2,
                ),
            )
            return response.text
        except Exception as e:
            error_msg = str(e)
            if "429" not in error_msg:
                raise

            # Distinguish: quota exhausted (limit: 0) vs temporary rate limit
            if "limit: 0" in error_msg or "quota" in error_msg.lower():
                raise QuotaExhaustedError(
                    "API key quota exhausted (limit: 0). "
                    "Get a new key at https://aistudio.google.com/apikey "
                    "or enable billing."
                )

            # Temporary rate limit — retry with delay
            match = re.search(r"retry in ([\d.]+)s", error_msg)
            wait_time = min(float(match.group(1)) + 2 if match else 15.0, 30.0)
            console.print(
                f"  [yellow]Rate limited. Waiting {wait_time:.0f}s "
                f"(attempt {attempt + 1}/{max_retries})...[/]"
            )
            time.sleep(wait_time)

    raise RuntimeError(f"Failed after {max_retries} retries")


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
                console.print(
                    "\n[bold red]API quota exhausted. Stopping extraction.[/]"
                    "\n[yellow]Get a new key at https://aistudio.google.com/apikey[/]"
                    f"\n[dim]Partial results: {len(knowledge_units)}/{len(segments)} segments processed[/]"
                )
                break

            except Exception as e:
                console.print(f"  [red]Error on {seg.segment_id}: {e}[/]")
                progress.update(task, advance=1)

    total_concepts = sum(len(ku.concepts) for ku in knowledge_units)
    total_rels = sum(len(ku.relationships) for ku in knowledge_units)
    console.print(
        f"\n[green]Extraction complete:[/] "
        f"{total_concepts} concepts, {total_rels} relationships "
        f"from {len(knowledge_units)} segments"
    )

    return knowledge_units
