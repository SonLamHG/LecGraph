"""Extract audio from video files or YouTube URLs."""

import re
import subprocess
import tempfile
from pathlib import Path

from rich.console import Console

console = Console(force_terminal=True)


def is_youtube_url(source: str) -> bool:
    patterns = [
        r"(https?://)?(www\.)?youtube\.com/watch\?v=",
        r"(https?://)?(www\.)?youtu\.be/",
        r"(https?://)?(www\.)?youtube\.com/embed/",
    ]
    return any(re.match(p, source) for p in patterns)


def is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in {".wav", ".mp3", ".flac", ".ogg", ".m4a"}


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run subprocess with UTF-8 encoding (fixes Windows cp1252 issues)."""
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    kwargs.setdefault("text", True)
    return subprocess.run(cmd, **kwargs)


def extract_from_youtube(url: str, output_dir: Path) -> tuple[Path, str]:
    """Download audio from YouTube and return (audio_path, video_title)."""
    console.print(f"[bold blue]Downloading audio from YouTube...[/]")

    # Get video title first
    result = _run(
        ["yt-dlp", "--get-title", url],
        capture_output=True,
        check=True,
    )
    video_title = result.stdout.strip()

    # Download audio as wav
    output_path = output_dir / "audio.wav"
    _run(
        [
            "yt-dlp",
            "-x",
            "--audio-format", "wav",
            "--audio-quality", "0",
            "-o", str(output_dir / "audio.%(ext)s"),
            url,
        ],
        check=True,
        capture_output=True,
    )

    # yt-dlp may save as different name, find the wav file
    wav_files = list(output_dir.glob("audio.*"))
    if not wav_files:
        raise FileNotFoundError("yt-dlp did not produce an audio file")

    audio_path = wav_files[0]

    # Convert to wav if not already
    if audio_path.suffix.lower() != ".wav":
        wav_path = output_dir / "audio.wav"
        _run(
            ["ffmpeg", "-i", str(audio_path), "-ar", "16000", "-ac", "1", str(wav_path), "-y"],
            check=True,
            capture_output=True,
        )
        audio_path.unlink()
        audio_path = wav_path

    console.print(f"[green]Downloaded:[/] {video_title}")
    return audio_path, video_title


def extract_from_video(video_path: Path, output_dir: Path) -> Path:
    """Extract audio from a local video file."""
    console.print(f"[bold blue]Extracting audio from video...[/]")

    output_path = output_dir / "audio.wav"
    _run(
        [
            "ffmpeg",
            "-i", str(video_path),
            "-ar", "16000",       # 16kHz sample rate (optimal for Whisper)
            "-ac", "1",           # mono
            "-vn",                # no video
            str(output_path),
            "-y",                 # overwrite
        ],
        check=True,
        capture_output=True,
    )

    console.print(f"[green]Audio extracted:[/] {output_path}")
    return output_path


def extract_audio(source: str, work_dir: Path | None = None) -> tuple[Path, str]:
    """
    Extract audio from source (YouTube URL or local file).

    Returns:
        (audio_path, video_title)
    """
    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix="lecgraph_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    if is_youtube_url(source):
        return extract_from_youtube(source, work_dir)

    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"File not found: {source}")

    if is_audio_file(source_path):
        console.print(f"[green]Using audio file directly:[/] {source_path}")
        return source_path, source_path.stem

    # Assume it's a video file
    audio_path = extract_from_video(source_path, work_dir)
    return audio_path, source_path.stem
