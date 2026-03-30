"""CLI entry point for LecGraph pipeline."""

import json
import hashlib
import os
import sys
import tempfile
from pathlib import Path

# Fix Windows console encoding for Unicode
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import settings
from src.pipeline import audio_extractor, transcriber, segmenter, extractor
from src.pipeline.postprocessor import deduplicate_concepts, build_unique_concepts
from src.pipeline.models import PipelineResult

console = Console(force_terminal=True)


def _generate_video_id(source: str) -> str:
    """Generate a short deterministic ID from the source."""
    h = hashlib.md5(source.encode()).hexdigest()[:8]
    return f"vid_{h}"


def _format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _print_summary(result: PipelineResult):
    """Print a summary of the pipeline results."""
    console.print()
    console.print(Panel(
        f"[bold]{result.video_title}[/]\n"
        f"Duration: {_format_timestamp(result.duration)} | "
        f"Segments: {len(result.segments)} | "
        f"Concepts: {sum(len(ku.concepts) for ku in result.knowledge_units)} | "
        f"Relationships: {sum(len(ku.relationships) for ku in result.knowledge_units)}",
        title="[bold green]Pipeline Complete",
        border_style="green",
    ))

    # Segments table
    table = Table(title="Segments", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", min_width=30)
    table.add_column("Time", width=15)
    table.add_column("Concepts", width=10, justify="center")
    table.add_column("Relations", width=10, justify="center")

    for i, ku in enumerate(result.knowledge_units):
        start = _format_timestamp(ku.timestamp.start)
        end = _format_timestamp(ku.timestamp.end)
        table.add_row(
            str(i + 1),
            ku.title,
            f"{start} -> {end}",
            str(len(ku.concepts)),
            str(len(ku.relationships)),
        )

    console.print(table)

    # All concepts
    console.print("\n[bold]All Concepts:[/]")
    for ku in result.knowledge_units:
        for c in ku.concepts:
            icon = {"core": "*", "supporting": "o", "mentioned": "-"}.get(c.importance, ".")
            console.print(f"  {icon} [bold]{c.name}[/] ({c.type}) — {c.definition[:80]}...")

    # All relationships
    console.print("\n[bold]All Relationships:[/]")
    for ku in result.knowledge_units:
        for r in ku.relationships:
            console.print(f"  {r.from_concept} --[{r.type}]--> {r.to_concept}")


@click.group()
def cli():
    """LecGraph — Transform lecture videos into knowledge graphs."""
    pass


@cli.command()
@click.argument("source")
@click.option("--output", "-o", default=None, help="Output JSON file path")
@click.option("--skip-extraction", is_flag=True, help="Skip LLM extraction (transcript + segments only)")
def process(source: str, output: str | None, skip_extraction: bool):
    """
    Process a video through the LecGraph pipeline.

    SOURCE can be a YouTube URL or a local video/audio file path.
    """
    console.print(Panel(
        f"[bold]LecGraph Pipeline[/]\n"
        f"Source: {source}\n"
        f"LLM: {settings.llm_model}\n"
        f"Whisper: {settings.whisper_model_size}",
        border_style="blue",
    ))

    video_id = _generate_video_id(source)
    work_dir = Path(tempfile.mkdtemp(prefix="lecgraph_"))

    # --- Stage 1: Audio Extraction ---
    console.print("\n[bold]--- Stage 1: Audio Extraction ---[/]")
    audio_path, video_title = audio_extractor.extract_audio(source, work_dir)

    # --- Stage 2: Transcription ---
    console.print("\n[bold]--- Stage 2: Transcription ---[/]")
    sentences = transcriber.transcribe(audio_path)

    if not sentences:
        console.print("[red]No speech detected in the audio. Aborting.[/]")
        return

    duration = sentences[-1].end

    # --- Stage 3: Segmentation ---
    console.print("\n[bold]--- Stage 3: Semantic Segmentation ---[/]")
    segments = segmenter.segment(sentences, video_id)

    # --- Stage 4: Knowledge Extraction ---
    knowledge_units = []
    if not skip_extraction:
        console.print("\n[bold]--- Stage 4: Knowledge Extraction ---[/]")

        if not settings.openai_api_key:
            console.print(
                "[red]OPENAI_API_KEY not set. "
                "Run with --skip-extraction or set the key in .env[/]"
            )
            return

        knowledge_units = extractor.extract_all(segments, video_id, video_title)

        # --- Stage 4b: Post-processing ---
        console.print("\n[bold]--- Stage 4b: Post-processing ---[/]")
        all_names_before = [c.name for ku in knowledge_units for c in ku.concepts]
        knowledge_units = deduplicate_concepts(knowledge_units)
        all_names_after = [c.name for ku in knowledge_units for c in ku.concepts]
        unique_before = len(set(all_names_before))
        unique_after = len(set(all_names_after))
        console.print(
            f"[dim]Deduplicated: {unique_before} unique names → {unique_after} "
            f"(definitions & relationships normalized)[/]"
        )
    else:
        console.print("\n[dim]Skipping LLM extraction (--skip-extraction)[/]")

    # --- Build Result ---
    unique_concepts = build_unique_concepts(knowledge_units) if knowledge_units else []
    result = PipelineResult(
        video_id=video_id,
        video_title=video_title,
        source=source,
        duration=duration,
        segments=segments,
        knowledge_units=knowledge_units,
        unique_concepts=unique_concepts,
    )

    # --- Save Output ---
    output_dir = settings.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if output is None:
        output = str(output_dir / f"{video_id}.json")

    output_path = Path(output)
    output_path.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    console.print(f"\n[bold green]Output saved to:[/] {output_path}")

    # --- Print Summary ---
    _print_summary(result)


@cli.command()
@click.argument("json_path")
def inspect(json_path: str):
    """Inspect a previously processed pipeline result."""
    path = Path(json_path)
    if not path.exists():
        console.print(f"[red]File not found: {path}[/]")
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    result = PipelineResult.model_validate(data)
    _print_summary(result)


@cli.command("build-graph")
@click.argument("json_path")
def build_graph(json_path: str):
    """Build Neo4j knowledge graph and ChromaDB index from pipeline output JSON."""
    path = Path(json_path)
    if not path.exists():
        console.print(f"[red]File not found: {path}[/]")
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    result = PipelineResult.model_validate(data)

    # Build graph
    from src.pipeline.graph_builder import build_graph as _build_graph
    graph_stats = _build_graph(result)

    # Index into ChromaDB
    from src.pipeline.indexer import index_pipeline_result
    index_stats = index_pipeline_result(result)

    console.print(Panel(
        f"[bold]Graph Build Complete[/]\n"
        f"Neo4j: {graph_stats}\n"
        f"ChromaDB: {index_stats}",
        title="[bold green]Done",
        border_style="green",
    ))


@cli.command()
@click.option("--host", default=None, help="Host to bind to")
@click.option("--port", default=None, type=int, help="Port to bind to")
def serve(host: str | None, port: int | None):
    """Start the FastAPI server."""
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    cli()
