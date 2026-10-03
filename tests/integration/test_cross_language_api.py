"""Integration test for cross-language API endpoint and contract resolution."""

from pathlib import Path

import pytest

from app.ingestion.repository_service import RepositoryIngestionService
from app.models.entities import IngestionResult


@pytest.mark.integration
def test_cross_language_api_resolution():
    fixture_path = Path("tests/fixtures/multi_language_repo").resolve()
    assert fixture_path.exists(), f"Fixture path {fixture_path} must exist"

    service = RepositoryIngestionService()
    result: IngestionResult = service.ingest_repository(str(fixture_path), force=True)

    assert result.status == "completed"
    assert result.files_processed >= 10

    # Query Neo4j for ApiEndpoint and ApiClientCall nodes
    client = service.graph_builder.client

    endpoints = client.execute_read(
        "MATCH (ep:ApiEndpoint) WHERE ep.repository_id = $repo_id RETURN ep.path AS path, ep.http_method AS method, ep.language AS lang",
        {"repo_id": result.repository_id},
    )
    assert len(endpoints) >= 1
    paths = {e["path"] for e in endpoints}
    assert "/api/users" in paths

    client_calls = client.execute_read(
        "MATCH (call:ApiClientCall) WHERE call.repository_id = $repo_id RETURN call.url AS url, call.http_method AS method, call.language AS lang",
        {"repo_id": result.repository_id},
    )
    assert len(client_calls) >= 1
    urls = {c["url"] for c in client_calls}
    assert "/api/users" in urls

    contracts = client.execute_read(
        "MATCH (c:ApiContract) WHERE c.repository_id = $repo_id RETURN c.path_template AS path, c.http_method AS method",
        {"repo_id": result.repository_id},
    )
    assert len(contracts) >= 1

    # Verify cross-language MATCHES_ENDPOINT relationship
    matches = client.execute_read(
        "MATCH (call:ApiClientCall)-[r:MATCHES_ENDPOINT]->(ep:ApiEndpoint) RETURN call.language AS client_lang, ep.language AS ep_lang, r.match_reason AS reason",
        {},
    )
    assert len(matches) >= 1
    cross_lang = [m for m in matches if m["client_lang"] != m["ep_lang"]]
    assert len(cross_lang) >= 1
    assert cross_lang[0]["reason"] in ("EXACT_METHOD_AND_PATH", "PATH_TEMPLATE_MATCH")
