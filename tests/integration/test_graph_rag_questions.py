"""Integration test for end-to-end Graph RAG reasoning questions on sample_repo."""

from pathlib import Path

import pytest

from app.embeddings.qdrant_store import QdrantStore
from app.graph.neo4j_client import Neo4jClient
from app.ingestion.repository_service import RepositoryIngestionService
from app.utils.exceptions import GraphDatabaseError, VectorStoreError
from app.workflows.graph_rag import GraphRAGPipeline


@pytest.mark.integration
def test_graph_rag_end_to_end_questions():
    """Ingest sample_repo and run 5 required end-to-end questions verifying real graph/vector grounding."""
    sample_path = str(Path("tests/fixtures/sample_repo").resolve())

    neo4j_client = Neo4jClient()
    qdrant_store = QdrantStore()

    try:
        neo4j_client.verify_connectivity()
        qdrant_store.ensure_collection(vector_size=384)
    except (GraphDatabaseError, VectorStoreError) as e:
        pytest.skip(f"Live database service unavailable for integration test: {e}")

    # 1. Ingest sample repository
    ingestion_service = RepositoryIngestionService()
    ingest_result = ingestion_service.ingest_repository(target=sample_path)
    assert ingest_result.status == "completed"
    assert ingest_result.files_processed > 0

    pipeline = GraphRAGPipeline()

    questions = [
        "Who calls UserService?",
        "What does UserService.create_user call?",
        "Trace the flow from main.py to UserRepository.",
        "What classes does UserService depend on?",
        "Explain how user creation works.",
    ]

    for q in questions:
        response = pipeline.run(question=q, repository_id=ingest_result.repository_id, debug=True)

        assert response.answer is not None
        assert len(response.answer.strip()) > 0
        assert response.validation_status is True
        assert len(response.retrieved_chunks) > 0, f"No chunks retrieved for question: '{q}'"
