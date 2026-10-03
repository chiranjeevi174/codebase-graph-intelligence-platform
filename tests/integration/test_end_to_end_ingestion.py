"""Integration test for end-to-end repository ingestion into live Neo4j & Qdrant instances."""

from pathlib import Path

import pytest

from app.embeddings.qdrant_store import QdrantStore
from app.graph.neo4j_client import Neo4jClient
from app.ingestion.repository_service import RepositoryIngestionService
from app.utils.exceptions import GraphDatabaseError, VectorStoreError


@pytest.mark.integration
def test_end_to_end_sample_repo_ingestion():
    sample_path = str(Path("tests/fixtures/sample_repo").resolve())

    neo4j_client = Neo4jClient()
    qdrant_store = QdrantStore()

    # Skip integration test if database services are unavailable
    try:
        neo4j_client.verify_connectivity()
        qdrant_store.ensure_collection(vector_size=384)
    except (GraphDatabaseError, VectorStoreError) as e:
        pytest.skip(f"Live Neo4j or Qdrant database service unavailable: {e}")

    service = RepositoryIngestionService()

    # 1. First Ingestion Run
    result1 = service.ingest_repository(target=sample_path)

    assert result1.status == "completed"
    assert result1.files_processed == 5
    assert result1.symbols_extracted > 0
    assert result1.chunks_created > 0
    assert result1.vectors_created > 0

    # 2. Verify Neo4j Graph Data
    repo_nodes = neo4j_client.execute_read(
        "MATCH (r:Repository {repository_id: $id}) RETURN r",
        {"id": result1.repository_id},
    )
    assert len(repo_nodes) == 1

    file_nodes = neo4j_client.execute_read(
        "MATCH (r:Repository {repository_id: $id})-[:CONTAINS]->(f:File) RETURN f",
        {"id": result1.repository_id},
    )
    assert len(file_nodes) == 5

    user_service_class = neo4j_client.execute_read(
        "MATCH (c:Class) WHERE c.name = 'UserService' RETURN c",
    )
    assert len(user_service_class) >= 1
    assert user_service_class[0]["c"]["start_line"] > 0

    # 3. Verify Qdrant Vector Data
    emb_service = service.embedding_service
    hits = emb_service.search_similar_code(query="user creation service", limit=3, repository_id=result1.repository_id)
    assert len(hits) > 0
    first_payload = hits[0]["payload"]
    assert first_payload["repository_id"] == result1.repository_id
    assert "start_line" in first_payload
    assert "end_line" in first_payload
    assert "file_path" in first_payload

    # 4. Re-ingest to verify Idempotency (no duplicate Repository or Class nodes)
    result2 = service.ingest_repository(target=sample_path)
    assert result2.status == "completed"

    repo_nodes_after = neo4j_client.execute_read(
        "MATCH (r:Repository {repository_id: $id}) RETURN r",
        {"id": result1.repository_id},
    )
    assert len(repo_nodes_after) == 1
