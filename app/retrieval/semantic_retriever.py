"""Semantic retriever component performing Qdrant vector retrieval and result normalization."""

from typing import Any

from app.embeddings.embedder import EmbeddingService
from app.models.entities import NormalizedSearchResult
from app.utils.logger import logger


class SemanticRetriever:
    """Retriever responsible for query embedding and semantic vector search in Qdrant."""

    def __init__(self, embedding_service: EmbeddingService | None = None):
        self.embedding_service = embedding_service or EmbeddingService()

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        repository_id: str | None = None,
        file_path: str | None = None,
        symbol_type: str | None = None,
    ) -> list[NormalizedSearchResult]:
        """Perform semantic retrieval and convert Qdrant hits into normalized search results."""
        if not query.strip():
            return []

        logger.info(f"Performing semantic search for query: '{query}' (limit={limit})")
        raw_results = self.embedding_service.search_similar_code(
            query=query,
            limit=limit,
            repository_id=repository_id,
        )

        normalized_results: list[NormalizedSearchResult] = []
        for res in raw_results:
            score = float(res.get("score", 0.0))
            chunk_id = str(res.get("chunk_id", ""))
            payload: dict[str, Any] = res.get("payload", {}) or {}

            repo_id = str(payload.get("repository_id") or repository_id or "default")
            fpath = str(payload.get("file_path") or "")
            sym_name = payload.get("symbol_name") or None
            qual_name = payload.get("qualified_name") or payload.get("parent_symbol") or sym_name
            sym_type = payload.get("symbol_type") or None
            start_l = int(payload.get("start_line", 1))
            end_l = int(payload.get("end_line", 1))
            content = str(payload.get("content") or "")

            normalized_results.append(
                NormalizedSearchResult(
                    id=chunk_id,
                    source="semantic",
                    repository_id=repo_id,
                    file_path=fpath,
                    symbol_name=sym_name,
                    qualified_name=qual_name,
                    symbol_type=sym_type,
                    start_line=start_l,
                    end_line=end_l,
                    content=content,
                    score=score,
                    rrf_score=0.0,
                )
            )

        return normalized_results
