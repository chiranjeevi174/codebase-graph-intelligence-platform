"""Qdrant Vector Database Store wrapper and point management."""

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models

from app.config.settings import Settings, get_settings
from app.models.entities import CodeChunk
from app.utils.exceptions import VectorStoreError
from app.utils.logger import logger


class QdrantStore:
    """Client abstraction for Qdrant Vector Database operations."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.collection_name = self.settings.QDRANT_COLLECTION
        self._client: QdrantClient | None = None

    def _get_client(self) -> QdrantClient:
        """Lazily initialize QdrantClient connection."""
        if self._client is None:
            try:
                self._client = QdrantClient(url=self.settings.QDRANT_URL)
            except Exception as e:
                raise VectorStoreError(f"Failed to connect to Qdrant at {self.settings.QDRANT_URL}: {e}")
        return self._client

    def ensure_collection(self, vector_size: int = 384):
        """Ensure vector collection exists with distance metric and payload indexes."""
        client = self._get_client()
        try:
            collections = [c.name for c in client.get_collections().collections]
            if self.collection_name not in collections:
                logger.info(f"Creating Qdrant collection '{self.collection_name}' (vector size {vector_size})...")
                client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=rest_models.VectorParams(
                        size=vector_size,
                        distance=rest_models.Distance.COSINE,
                    ),
                )

                # Create payload indexes for metadata filtering
                for field in ["repository_id", "file_path", "language", "symbol_type", "symbol_name"]:
                    client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field,
                        field_schema=rest_models.PayloadSchemaType.KEYWORD,
                    )
        except Exception as e:
            raise VectorStoreError(f"Failed to ensure Qdrant collection '{self.collection_name}': {e}")

    def upsert_chunks(self, chunks: list[CodeChunk], embeddings: list[list[float]]):
        """Upsert embedded code chunks into Qdrant vector database."""
        if not chunks or not embeddings:
            return
        if len(chunks) != len(embeddings):
            raise VectorStoreError("Mismatch between chunk count and embedding count.")

        client = self._get_client()
        self.ensure_collection(vector_size=len(embeddings[0]))

        points = []
        for chunk, emb in zip(chunks, embeddings):
            payload = {
                "chunk_id": chunk.chunk_id,
                "repository_id": chunk.repository_id,
                "file_path": chunk.file_path,
                "language": chunk.language,
                "module": chunk.module or "",
                "symbol_name": chunk.symbol_name or "",
                "symbol_type": chunk.symbol_type or "",
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "content": chunk.content,
                "parent_symbol": chunk.parent_symbol or "",
                "commit_hash": chunk.commit_hash or "",
                **chunk.metadata,
            }
            points.append(
                rest_models.PointStruct(
                    id=chunk.chunk_id,
                    vector=emb,
                    payload=payload,
                )
            )

        try:
            client.upsert(collection_name=self.collection_name, points=points)
            logger.info(f"Successfully upserted {len(points)} vector points to Qdrant collection '{self.collection_name}'.")
        except Exception as e:
            raise VectorStoreError(f"Failed to upsert points into Qdrant: {e}")

    def search_similar(
        self,
        query_vector: list[float],
        limit: int = 5,
        repository_id: str | None = None,
        file_path: str | None = None,
        symbol_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search similar vector points with optional payload filters."""
        client = self._get_client()

        must_filters = []
        if repository_id:
            must_filters.append(rest_models.FieldCondition(key="repository_id", match=rest_models.MatchValue(value=repository_id)))
        if file_path:
            must_filters.append(rest_models.FieldCondition(key="file_path", match=rest_models.MatchValue(value=file_path)))
        if symbol_type:
            must_filters.append(rest_models.FieldCondition(key="symbol_type", match=rest_models.MatchValue(value=symbol_type)))

        query_filter = rest_models.Filter(must=must_filters) if must_filters else None

        try:
            response = client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
            )
            hits = response.points
            return [
                {
                    "score": hit.score,
                    "chunk_id": hit.id,
                    "payload": hit.payload,
                }
                for hit in hits
            ]
        except Exception as e:
            raise VectorStoreError(f"Vector search failed in Qdrant: {e}")
