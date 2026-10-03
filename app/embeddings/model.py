"""Embedding abstraction using Hugging Face sentence-transformers."""

from abc import ABC, abstractmethod

from app.config.settings import Settings, get_settings
from app.utils.exceptions import EmbeddingError
from app.utils.logger import logger


class BaseEmbedder(ABC):
    """Abstract interface for text and code embedders."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string into vector representation."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text strings into vector representations."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return embedding vector dimensionality."""


class HuggingFaceEmbedder(BaseEmbedder):
    """Embedder implementation using Hugging Face sentence-transformers (BAAI/bge-small-en-v1.5)."""

    def __init__(self, model_name: str | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.model_name = model_name or self.settings.EMBEDDING_MODEL
        self._model = None
        self._dimension: int | None = None

    def _load_model(self):
        """Lazy load sentence-transformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading Hugging Face embedding model: '{self.model_name}'...")
                self._model = SentenceTransformer(self.model_name)
                # Compute sample vector to determine dimension
                dummy_vec = self._model.encode("test", convert_to_numpy=True)
                self._dimension = len(dummy_vec)
                logger.info(f"Loaded embedding model '{self.model_name}' with dimension {self._dimension}.")
            except Exception as e:
                raise EmbeddingError(f"Failed to load Hugging Face embedding model '{self.model_name}': {e}")

    def embed_text(self, text: str) -> list[float]:
        """Embed single string into vector list."""
        self._load_model()
        if self._model is None:
            raise EmbeddingError(f"Embedding model '{self.model_name}' is not loaded.")
        try:
            vec = self._model.encode(text, normalize_embeddings=True)
            return vec.tolist()
        except Exception as e:
            raise EmbeddingError(f"Failed to embed text: {e}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Batch embed list of documents/code snippets."""
        if not texts:
            return []
        self._load_model()
        if self._model is None:
            raise EmbeddingError(f"Embedding model '{self.model_name}' is not loaded.")
        try:
            vecs = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return vecs.tolist()
        except Exception as e:
            raise EmbeddingError(f"Failed to embed document batch: {e}")

    @property
    def dimension(self) -> int:
        """Get vector dimension."""
        self._load_model()
        return self._dimension or 384
