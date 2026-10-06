"""Unit tests for configuration loading."""

from app.config.settings import Settings, get_settings


def test_settings_default_values():
    settings = Settings()
    assert settings.APP_NAME == "Codebase Graph Intelligence Platform"
    assert settings.NEO4J_URI == "bolt://localhost:7687"
    assert settings.QDRANT_URL == "http://localhost:6333"
    assert settings.EMBEDDING_MODEL == "BAAI/bge-small-en-v1.5"
    assert settings.LLM_PROVIDER == "openai"


def test_get_settings_caching():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
