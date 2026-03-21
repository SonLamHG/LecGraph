"""Semantic segmentation using TextTiling with sentence embeddings."""

import numpy as np
from rich.console import Console

from src.config import settings
from src.pipeline.models import Segment, Sentence

console = Console(force_terminal=True)


def _load_embedding_model():
    """Load sentence-transformers model."""
    from sentence_transformers import SentenceTransformer

    console.print(f"[bold blue]Loading embedding model:[/] {settings.embedding_model}")
    model = SentenceTransformer(settings.embedding_model)
    return model


def _embed_sentences(model, sentences: list[Sentence]) -> np.ndarray:
    """Embed all sentences into vectors."""
    texts = [s.text for s in sentences]
    embeddings = model.encode(texts, show_progress_bar=False, batch_size=32)
    return np.array(embeddings)


def _cosine_similarity_consecutive(embeddings: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between consecutive sentence pairs."""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-10)  # avoid division by zero
    normalized = embeddings / norms

    # sim[i] = cosine(sentence[i], sentence[i+1])
    similarities = np.sum(normalized[:-1] * normalized[1:], axis=1)
    return similarities


def _smooth(values: np.ndarray, window: int) -> np.ndarray:
    """Apply moving average smoothing."""
    if window <= 1 or len(values) <= window:
        return values
    kernel = np.ones(window) / window
    # Pad edges to maintain array length
    padded = np.pad(values, (window // 2, window // 2), mode="edge")
    smoothed = np.convolve(padded, kernel, mode="valid")
    return smoothed[:len(values)]


def _find_boundaries(
    similarities: np.ndarray,
    sentences: list[Sentence],
    min_duration: float,
    max_duration: float,
) -> list[int]:
    """
    Find topic boundaries as local minima in the similarity curve.

    Returns list of sentence indices where boundaries occur.
    """
    if len(similarities) < 3:
        return []

    # Find local minima: sim[i] < sim[i-1] and sim[i] < sim[i+1]
    candidates = []
    for i in range(1, len(similarities) - 1):
        if similarities[i] < similarities[i - 1] and similarities[i] < similarities[i + 1]:
            candidates.append(i)

    if not candidates:
        # Fallback: use global minimum
        candidates = [int(np.argmin(similarities))]

    # Compute depth score for each candidate
    # Depth = how much the similarity drops compared to surrounding peaks
    scored = []
    for idx in candidates:
        left_peak = max(similarities[max(0, idx - 5):idx + 1])
        right_peak = max(similarities[idx:min(len(similarities), idx + 6)])
        depth = ((left_peak - similarities[idx]) + (right_peak - similarities[idx])) / 2
        scored.append((idx, depth))

    # Sort by depth (deepest drops first — strongest topic changes)
    scored.sort(key=lambda x: x[1], reverse=True)

    # Greedily select boundaries that respect min/max duration constraints
    # Boundary at index i means: split between sentence[i] and sentence[i+1]
    boundaries = []
    for idx, depth in scored:
        boundary_time = sentences[idx + 1].start

        # Check min duration against all existing boundaries
        valid = True
        all_points = sorted([0.0] + [sentences[b + 1].start for b in boundaries] + [boundary_time])

        for j in range(len(all_points) - 1):
            if all_points[j + 1] - all_points[j] < min_duration:
                valid = False
                break

        if valid:
            boundaries.append(idx)

    # Also check max_duration: force split long segments
    boundaries_sorted = sorted(boundaries)
    final_boundaries = list(boundaries_sorted)

    # Build segments and check max duration
    split_points = [0] + [b + 1 for b in final_boundaries] + [len(sentences)]
    for i in range(len(split_points) - 1):
        seg_start = sentences[split_points[i]].start
        seg_end = sentences[split_points[i + 1] - 1].end
        duration = seg_end - seg_start

        if duration > max_duration:
            # Force split at midpoint
            mid_sent = (split_points[i] + split_points[i + 1]) // 2
            if mid_sent - 1 not in final_boundaries and mid_sent > split_points[i]:
                final_boundaries.append(mid_sent - 1)

    return sorted(set(final_boundaries))


def _build_segments(
    sentences: list[Sentence],
    boundaries: list[int],
    video_id: str,
) -> list[Segment]:
    """Build Segment objects from boundary indices."""
    split_points = [0] + [b + 1 for b in boundaries] + [len(sentences)]
    segments = []

    for i in range(len(split_points) - 1):
        start_idx = split_points[i]
        end_idx = split_points[i + 1]
        seg_sentences = sentences[start_idx:end_idx]

        if not seg_sentences:
            continue

        transcript = " ".join(s.text for s in seg_sentences)

        segments.append(Segment(
            segment_id=f"{video_id}_seg{i + 1:03d}",
            title=f"Segment {i + 1}",  # Will be named by LLM later
            start=seg_sentences[0].start,
            end=seg_sentences[-1].end,
            transcript=transcript,
            sentences=seg_sentences,
        ))

    return segments


def _merge_short_segments(
    segments: list[Segment],
    min_duration: float,
) -> list[Segment]:
    """Merge segments shorter than min_duration into their neighbor."""
    if len(segments) <= 1:
        return segments

    merged = True
    while merged:
        merged = False
        for i in range(len(segments)):
            duration = segments[i].end - segments[i].start
            if duration < min_duration and len(segments) > 1:
                if i == len(segments) - 1:
                    target = i - 1
                elif i == 0:
                    target = 1
                else:
                    prev_dur = segments[i - 1].end - segments[i - 1].start
                    next_dur = segments[i + 1].end - segments[i + 1].start
                    target = i - 1 if prev_dur <= next_dur else i + 1

                a, b = min(i, target), max(i, target)
                merged_seg = Segment(
                    segment_id=segments[a].segment_id,
                    title=segments[a].title,
                    start=segments[a].start,
                    end=segments[b].end,
                    transcript=segments[a].transcript + " " + segments[b].transcript,
                    sentences=segments[a].sentences + segments[b].sentences,
                )
                segments = segments[:a] + [merged_seg] + segments[b + 1:]

                base_id = segments[0].segment_id.rsplit("_seg", 1)[0]
                for j, seg in enumerate(segments):
                    seg.segment_id = f"{base_id}_seg{j + 1:03d}"

                merged = True
                break

    return segments


def segment(
    sentences: list[Sentence],
    video_id: str = "vid01",
) -> list[Segment]:
    """
    Segment transcript into topic-coherent chunks using TextTiling.

    Args:
        sentences: List of transcribed sentences with timestamps
        video_id: Identifier for the video

    Returns:
        List of Segment objects
    """
    if len(sentences) <= 1:
        # Single sentence or empty: return as one segment
        transcript = " ".join(s.text for s in sentences)
        return [Segment(
            segment_id=f"{video_id}_seg001",
            title="Full transcript",
            start=sentences[0].start if sentences else 0.0,
            end=sentences[-1].end if sentences else 0.0,
            transcript=transcript,
            sentences=sentences,
        )]

    console.print(f"[bold blue]Segmenting {len(sentences)} sentences...[/]")

    # Step 1: Embed sentences
    model = _load_embedding_model()
    embeddings = _embed_sentences(model, sentences)
    console.print(f"[dim]Embedded {len(sentences)} sentences[/]")

    # Step 2: Compute consecutive cosine similarity
    similarities = _cosine_similarity_consecutive(embeddings)

    # Step 3: Smooth
    smoothed = _smooth(similarities, settings.similarity_smoothing_window)

    # Step 4: Find boundaries
    boundaries = _find_boundaries(
        smoothed,
        sentences,
        min_duration=settings.segment_min_duration,
        max_duration=settings.segment_max_duration,
    )

    console.print(f"[dim]Found {len(boundaries)} topic boundaries[/]")

    # Step 5: Build segments
    segments = _build_segments(sentences, boundaries, video_id)

    # Step 6: Merge short segments
    segments = _merge_short_segments(segments, min_duration=settings.segment_min_duration)

    for seg in segments:
        duration = seg.end - seg.start
        console.print(
            f"  [dim]• {seg.segment_id}:[/] {duration:.0f}s, "
            f"{len(seg.sentences)} sentences"
        )

    console.print(f"[green]Segmentation complete:[/] {len(segments)} segments")
    return segments
