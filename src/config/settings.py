from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gemini
    gemini_api_key: str = ""

    # Whisper
    whisper_model_size: str = "large-v3"
    whisper_device: str = "auto"
    whisper_compute_type: str = "float16"

    # Embedding
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # Segmentation
    segment_min_duration: float = 30.0
    segment_max_duration: float = 1200.0
    similarity_smoothing_window: int = 3

    # LLM
    llm_model: str = "gemini-2.0-flash"
    llm_max_tokens: int = 4096

    # Output
    output_dir: Path = Path("output")
