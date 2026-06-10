from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: Optional[str] = None
    serpapi_api_key: Optional[str] = None

    chroma_dir: str = "./data/chroma"
    chroma_collection: str = "user_travel_reviews"
    openai_embedding_model: str = "text-embedding-3-small"

    spacy_model: str = "en_core_web_sm"
    min_results: int = 3
    rag_max_distance: float = 1.35

    serpapi_timeout_seconds: int = 25
    serpapi_hl: str = "en"
    serpapi_gl: str = "it"

    frontend_origin: str = "http://localhost:5173"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
