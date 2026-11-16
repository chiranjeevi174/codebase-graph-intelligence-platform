"""Query and Graph RAG reasoning API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.entities import GraphRAGResponse
from app.utils.logger import logger
from app.workflows.graph_rag import GraphRAGPipeline

router = APIRouter(tags=["Query"])


class QueryRequest(BaseModel):
    question: str = Field(..., description="Developer natural language query about codebase")
    repository_id: str | None = Field(None, description="Optional target repository filter")
    graph_top_k: int = Field(10, description="Top K graph relationships to retrieve")
    semantic_top_k: int = Field(10, description="Top K vector chunks to retrieve")
    final_top_k: int = Field(10, description="Top K RRF fused results to return")
    max_hops: int = Field(2, description="Maximum graph traversal hops")
    debug: bool = Field(False, description="Enable debug trace mode returning retrieval steps")


@router.post("/query", response_model=GraphRAGResponse)
def execute_query(request: QueryRequest):
    """Execute Graph RAG multi-hop graph reasoning workflow over codebase."""
    sanitized_q = request.question.strip()[:100]
    logger.info(f"[QueryAPI] Received query request: '{sanitized_q}' (repo_id={request.repository_id})")
    try:
        pipeline = GraphRAGPipeline()
        response = pipeline.run(
            question=request.question,
            repository_id=request.repository_id,
            graph_top_k=request.graph_top_k,
            semantic_top_k=request.semantic_top_k,
            final_top_k=request.final_top_k,
            max_hops=request.max_hops,
            debug=request.debug,
        )
        logger.info(
            f"[QueryAPI] Query response prepared. validation_status={response.validation_status} "
            f"errors={len(response.validation_errors)} sources={len(response.sources)} "
            f"paths={len(response.graph_paths)}"
        )
        return response
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 # FastAPI 500 error boundary
        logger.error(f"[QueryAPI] Query execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Graph RAG query execution failed: {e}")
