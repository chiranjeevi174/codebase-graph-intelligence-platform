"""Integration test for multi-language repository ingestion."""

from pathlib import Path

import pytest

from app.ingestion.repository_service import RepositoryIngestionService
from app.models.entities import IngestionResult


@pytest.mark.integration
def test_multilanguage_repository_ingestion():
    fixture_path = Path("tests/fixtures/multi_language_repo").resolve()
    assert fixture_path.exists(), f"Fixture path {fixture_path} must exist"

    service = RepositoryIngestionService()
    result: IngestionResult = service.ingest_repository(str(fixture_path), force=True)

    # 1. Ingestion status and summary verification
    assert result.status == "completed"
    assert result.files_discovered >= 10
    assert result.files_processed >= 10
    assert result.files_failed == 0
    assert result.symbols_extracted > 0
    assert result.relationships_extracted > 0
    assert result.chunks_created > 0
    assert result.graph_nodes_created > 0
    assert result.graph_relationships_created > 0
    assert result.vectors_created > 0

    # 2. Verify Neo4j graph nodes and languages
    repo_nodes = service.graph_builder.client.execute_read(
        "MATCH (f:File {file_id: $file_id}) RETURN f.language AS language",
        {"file_id": f"{result.repository_id}:python/service.py"},
    )
    if repo_nodes:
        assert repo_nodes[0]["language"] == "python"

    # Verify multi-language file nodes exist in Neo4j
    all_languages = service.graph_builder.client.execute_read(
        "MATCH (f:File) WHERE f.file_id STARTS WITH $repo_id RETURN DISTINCT f.language AS lang",
        {"repo_id": result.repository_id},
    )
    langs_in_graph = {record["lang"] for record in all_languages}
    assert "python" in langs_in_graph
    assert "javascript" in langs_in_graph
    assert "typescript" in langs_in_graph
    assert "java" in langs_in_graph
    assert "go" in langs_in_graph

    # 3. Verify Qdrant points payload contains language metadata
    from qdrant_client.http import models as rest_models

    qdrant_client = service.embedding_service.qdrant_store._get_client()
    collection_name = service.embedding_service.qdrant_store.collection_name

    repo_filter = rest_models.Filter(
        must=[
            rest_models.FieldCondition(
                key="repository_id",
                match=rest_models.MatchValue(value=result.repository_id),
            )
        ]
    )

    all_points = []
    next_offset = None
    while True:
        points, next_offset = qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter=repo_filter,
            limit=100,
            with_payload=True,
            offset=next_offset,
        )
        all_points.extend(points)
        if not next_offset:
            break

    payload_languages = {
        p.payload.get("language") for p in all_points if p.payload and p.payload.get("language")
    }

    assert "python" in payload_languages
    assert "javascript" in payload_languages
    assert "typescript" in payload_languages
    assert "java" in payload_languages
    assert "go" in payload_languages
