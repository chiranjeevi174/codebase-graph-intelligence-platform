"""Integration tests for Qdrant vector database connection."""

import pytest

from app.embeddings.qdrant_store import QdrantStore
from app.utils.exceptions import VectorStoreError


@pytest.mark.integration
def test_qdrant_connection_or_handled_error():
    store = QdrantStore()
    try:
        store.ensure_collection(vector_size=384)
    except VectorStoreError as e:
        pytest.skip(f"Qdrant Docker service not running: {e}")
