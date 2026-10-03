"""Integration test for Code Impact Analysis Engine on ingested sample_repo."""

from pathlib import Path

import pytest

from app.analysis.impact_service import CodeImpactAnalysisService
from app.embeddings.qdrant_store import QdrantStore
from app.graph.neo4j_client import Neo4jClient
from app.ingestion.repository_service import RepositoryIngestionService
from app.models.entities import ImpactAnalysisRequest
from app.utils.exceptions import GraphDatabaseError, VectorStoreError


@pytest.mark.integration
def test_impact_analysis_sample_repo():
    """Verify live impact analysis for UserService.create_user on sample_repo."""
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

    # 2. Run Impact Analysis for UserService.create_user
    service = CodeImpactAnalysisService()
    request = ImpactAnalysisRequest(
        symbol="UserService.create_user",
        repository_id=ingest_result.repository_id,
        max_hops=3,
    )

    result = service.analyze_impact(request)

    assert result.target is not None
    assert len(result.explanation.strip()) > 0
    assert result.summary.affected_files_count > 0
    assert len(result.affected_files) > 0
