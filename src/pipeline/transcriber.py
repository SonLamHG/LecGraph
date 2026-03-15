"""Transcribe audio to text with timestamps using Whisper."""

from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config import settings
from src.pipeline.models import Sentence, Word

console = Console()

# Punctuation that ends a sentence
SENTENCE_ENDINGS = {".", "?", "!", "。", "？", "！"}

# Minimum pause (seconds) between words to force a sentence break
PAUSE_THRESHOLD = 1.0

# Maximum words per sentence before forcing a break
MAX_WORDS_PER_SENTENCE = 50


def _load_model():
    """Load the faster-whisper model."""
    from faster_whisper import WhisperModel

    device = settings.whisper_device
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    compute_type = settings.whisper_compute_type
    if device == "cpu" and compute_type == "float16":
        compute_type = "int8"

    console.print(
        f"[bold blue]Loading Whisper model:[/] {settings.whisper_model_size} "
        f"(device={device}, compute={compute_type})"
    )

    model = WhisperModel(
        settings.whisper_model_size,
        device=device,
        compute_type=compute_type,
    )
    return model


def _extract_words(model, audio_path: Path) -> list[Word]:
    """Run Whisper and extract word-level timestamps."""
    segments_iter, info = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        vad_filter=True,        # Filter out silence
        vad_parameters=dict(
            min_silence_duration_ms=500,
        ),
    )

    console.print(
        f"[dim]Detected language: {info.language} "
        f"(probability: {info.language_probability:.2f})[/]"
    )

    words = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Transcribing...", total=None)

        for segment in segments_iter:
            if segment.words:
                for w in segment.words:
                    words.append(Word(
                        text=w.word.strip(),
                        start=round(w.start, 3),
                        end=round(w.end, 3),
                        confidence=round(w.probability, 3),
                    ))
            progress.update(task, description=f"Transcribing... {len(words)} words")

    console.print(f"[green]Transcription complete:[/] {len(words)} words extracted")
    return words


def _group_into_sentences(words: list[Word]) -> list[Sentence]:
    """
    Group words into sentences based on:
    1. Punctuation (., ?, !)
    2. Pause duration between words (> PAUSE_THRESHOLD)
    3. Maximum word count per sentence
    """
    if not words:
        return []

    sentences = []
    current_words: list[Word] = []

    for i, word in enumerate(words):
        current_words.append(word)

        # Check if we should end the sentence
        ends_with_punct = any(word.text.endswith(p) for p in SENTENCE_ENDINGS)

        has_long_pause = False
        if i + 1 < len(words):
            gap = words[i + 1].start - word.end
            has_long_pause = gap > PAUSE_THRESHOLD

        too_many_words = len(current_words) >= MAX_WORDS_PER_SENTENCE

        if ends_with_punct or has_long_pause or too_many_words:
            text = " ".join(w.text for w in current_words)
            avg_conf = sum(w.confidence for w in current_words) / len(current_words)

            sentences.append(Sentence(
                text=text,
                start=round(current_words[0].start, 3),
                end=round(current_words[-1].end, 3),
                confidence=round(avg_conf, 3),
            ))
            current_words = []

    # Don't forget remaining words
    if current_words:
        text = " ".join(w.text for w in current_words)
        avg_conf = sum(w.confidence for w in current_words) / len(current_words)

        sentences.append(Sentence(
            text=text,
            start=round(current_words[0].start, 3),
            end=round(current_words[-1].end, 3),
            confidence=round(avg_conf, 3),
        ))

    console.print(f"[green]Grouped into:[/] {len(sentences)} sentences")
    return sentences


def transcribe(audio_path: Path) -> list[Sentence]:
    """
    Transcribe audio file to list of sentences with timestamps.

    Args:
        audio_path: Path to audio file (wav/mp3)

    Returns:
        List of Sentence objects with text, start, end, confidence
    """
    model = _load_model()
    words = _extract_words(model, audio_path)
    sentences = _group_into_sentences(words)
    return sentences
