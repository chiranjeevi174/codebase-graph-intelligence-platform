"""Embedding service orchestrating document vectorization and Qdrant ingestion."""


from app.embeddings.model import BaseEmbedder, HuggingFaceEmbedder
from app.embeddings.qdrant_store import QdrantStore
from app.models.entities import CodeChunk
from app.utils.logger import logger


class EmbeddingService:
    """Service for processing code chunks into embeddings and storing vectors in Qdrant."""

    def __init__(self, embedder: BaseEmbedder | None = None, qdrant_store: QdrantStore | None = None):
        self.embedder = embedder or HuggingFaceEmbedder()
        self.qdrant_store = qdrant_store or QdrantStore()

    def process_and_store_chunks(self, chunks: list[CodeChunk]):
        """Vectorizes code chunks and upserts them into Qdrant."""
        if not chunks:
            return

        texts = [chunk.content for chunk in chunks]
        logger.info(f"Generating embeddings for {len(texts)} code chunks...")
        embeddings = self.embedder.embed_documents(texts)
        self.qdrant_store.upsert_chunks(chunks, embeddings)

    def search_similar_code(
        self,
        query: str,
        limit: int = 5,
        repository_id: str | None = None,
    ):
        """Generates query embedding and performs similarity search in Qdrant vector store."""
        query_vector = self.embedder.embed_text(query)
        return self.qdrant_store.search_similar(query_vector, limit=limit, repository_id=repository_id)
