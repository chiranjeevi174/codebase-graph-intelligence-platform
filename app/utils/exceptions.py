"""Custom exception hierarchy for Codebase Graph Intelligence Platform."""


class PlatformError(Exception):
    """Base exception class for all platform exceptions."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(PlatformError):
    """Raised when there is an invalid or missing configuration."""


class RepositoryIngestionError(PlatformError):
    """Raised when loading or scanning a repository fails."""


class ParserError(PlatformError):
    """Raised when source code parsing or relationship extraction fails."""


class GraphDatabaseError(PlatformError):
    """Raised when interacting with Neo4j graph database fails."""


class VectorStoreError(PlatformError):
    """Raised when interacting with Qdrant vector database fails."""


class LLMProviderError(PlatformError):
    """Raised when interacting with an LLM provider fails."""


class EmbeddingError(PlatformError):
    """Raised when text or code embedding generation fails."""
