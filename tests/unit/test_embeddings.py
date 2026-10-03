"""Unit tests for embedding abstraction and Qdrant store integration."""

from unittest.mock import MagicMock

from app.embeddings.model import BaseEmbedder
from app.embeddings.qdrant_store import QdrantStore
from app.models.entities import CodeChunk


class DummyEmbedder(BaseEmbedder):
    def embed_text(self, text: str):
        return [0.1, 0.2, 0.3]

    def embed_documents(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]

    @property
    def dimension(self) -> int:
        return 3


def test_dummy_embedder():
    embedder = DummyEmbedder()
    vec = embedder.embed_text("def hello(): pass")
    assert len(vec) == 3
    assert embedder.dimension == 3


def test_qdrant_store_upsert_mock():
    mock_qdrant_client = MagicMock()
    store = QdrantStore()
    store._client = mock_qdrant_client

    chunk = CodeChunk(
        chunk_id="chunk1",
        repository_id="test_repo",
        file_path="main.py",
        start_line=1,
        end_line=5,
        content="def hello(): pass",
    )

    store.upsert_chunks([chunk], [[0.1, 0.2, 0.3]])
    mock_qdrant_client.upsert.assert_called_once()
