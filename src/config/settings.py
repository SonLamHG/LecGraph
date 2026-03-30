from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str = ""

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
    llm_model: str = "gpt-4o-mini"
    llm_max_tokens: int = 4096
    llm_max_workers: int = 5

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "neo4j"

    # ChromaDB
    chroma_persist_dir: str = "data/chroma"

    # Entity Resolution
    entity_resolution_similarity_threshold: float = 0.75

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: list[str] = ["http://localhost:3000"]

    # Output
    output_dir: Path = Path("output")
