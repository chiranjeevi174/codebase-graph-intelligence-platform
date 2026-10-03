"""Configuration settings using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application settings
    APP_NAME: str = "Codebase Graph Intelligence Platform"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["text", "json"] = "text"
    CORS_ORIGINS: list[str] = ["*"]
    RATE_LIMIT_PER_MINUTE: int = 120
    SECURITY_MAX_REQUEST_SIZE_BYTES: int = 10_485_760  # 10 MB
    GRAPH_MAX_HOPS: int = 3
    GRAPH_MAX_NODES: int = 50
    GRAPH_MAX_RELATIONSHIPS: int = 100

    # Timeout boundaries (seconds)
    NEO4J_TIMEOUT_SECONDS: float = 10.0
    QDRANT_TIMEOUT_SECONDS: float = 10.0
    REDIS_TIMEOUT_SECONDS: float = 5.0
    LLM_TIMEOUT_SECONDS: float = 30.0

    # Neo4j settings
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"

    # Qdrant settings
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "codebase_chunks"

    # Redis Queue & Worker settings
    REDIS_URL: str = "redis://localhost:6379"
    JOB_TTL_SECONDS: int = 86400
    IDEMPOTENCY_TTL_SECONDS: int = 86400
    WORKER_MAX_JOBS: int = 10
    WORKER_JOB_TIMEOUT: int = 300
    WORKER_MAX_TRIES: int = 3
    WORKER_HEALTH_CHECK_INTERVAL: int = 60

    # Embedding model
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    # LLM Provider selection
    LLM_PROVIDER: Literal["groq", "gemini", "openai"] = "groq"

    # Provider specific settings
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # PR & Webhook Integration settings
    GITHUB_WEBHOOK_SECRET: str = ""
    GITLAB_WEBHOOK_SECRET: str = ""
    GITHUB_TOKEN: str = ""
    GITLAB_TOKEN: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of Settings."""
    return Settings()
