from __future__ import annotations

"""Configuration for the AI learning core."""

from functools import lru_cache
import os
from pathlib import Path

from pydantic import Field
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - pydantic-settings is part of requirements
    from pydantic import BaseModel as BaseSettings

    def SettingsConfigDict(**kwargs):  # type: ignore[no-redef]
        return kwargs


try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is installed from requirements in normal use
    load_dotenv = None

if load_dotenv:
    load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ai_provider: str = Field(default="openai", alias="AI_PROVIDER")
    embedding_provider: str = Field(default="openai", alias="EMBEDDING_PROVIDER")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")

    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")
    gemini_embedding_model: str = Field(default="models/text-embedding-004", alias="GEMINI_EMBEDDING_MODEL")

    huggingface_embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        alias="HUGGINGFACE_EMBEDDING_MODEL",
    )
    huggingface_cache_folder: str | None = Field(default=None, alias="HUGGINGFACE_CACHE_FOLDER")

    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")

    vector_db_dir: str = Field(default="./vector_db", alias="VECTOR_DB_DIR")
    chunk_size: int = Field(default=1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=150, alias="CHUNK_OVERLAP")
    top_k: int = Field(default=5, alias="TOP_K")
    rag_chunk_max_chars: int = Field(default=1200, alias="RAG_CHUNK_MAX_CHARS")
    rag_context_max_chars: int = Field(default=5000, alias="RAG_CONTEXT_MAX_CHARS")

    def __init__(self, **data):
        """Create settings, falling back to os.environ if pydantic-settings is absent."""

        if not data and BaseSettings.__module__.startswith("pydantic."):
            data = {
                "AI_PROVIDER": os.getenv("AI_PROVIDER", "openai"),
                "EMBEDDING_PROVIDER": os.getenv("EMBEDDING_PROVIDER", "openai"),
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
                "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                "OPENAI_EMBEDDING_MODEL": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
                "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
                "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
                "GEMINI_EMBEDDING_MODEL": os.getenv("GEMINI_EMBEDDING_MODEL", "models/text-embedding-004"),
                "HUGGINGFACE_EMBEDDING_MODEL": os.getenv(
                    "HUGGINGFACE_EMBEDDING_MODEL",
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                ),
                "HUGGINGFACE_CACHE_FOLDER": os.getenv("HUGGINGFACE_CACHE_FOLDER"),
                "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY"),
                "DEEPSEEK_MODEL": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                "VECTOR_DB_DIR": os.getenv("VECTOR_DB_DIR", "./vector_db"),
                "CHUNK_SIZE": int(os.getenv("CHUNK_SIZE", "1000")),
                "CHUNK_OVERLAP": int(os.getenv("CHUNK_OVERLAP", "150")),
                "TOP_K": int(os.getenv("TOP_K", "5")),
                "RAG_CHUNK_MAX_CHARS": int(os.getenv("RAG_CHUNK_MAX_CHARS", "1200")),
                "RAG_CONTEXT_MAX_CHARS": int(os.getenv("RAG_CONTEXT_MAX_CHARS", "5000")),
            }
        super().__init__(**data)

    @property
    def vector_db_path(self) -> Path:
        """Return the vector database directory as a Path."""

        return Path(self.vector_db_dir)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()

