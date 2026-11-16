"""Unit tests for UI static mounting and new frontend API endpoints."""

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_health_check_endpoint():
    """Verify GET /health returns expected database status and provider fields."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "llm_provider" in data
    assert "embedding_model" in data
    assert "databases" in data


def test_static_frontend_index_serving():
    """Verify frontend HTML root page is served cleanly at /."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Code Graph Intelligence" in response.text or "<!DOCTYPE html>" in response.text


def test_frontend_navigation_six_primary_features():
    """Verify the frontend HTML navigation reflects exactly the six primary features and excludes standalone diff."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # Verify the six primary feature tabs exist in navigation
    assert 'data-tab="query"' in html
    assert 'data-tab="impact"' in html
    assert 'data-tab="apiflow"' in html
    assert 'data-tab="pr"' in html
    assert 'data-tab="architecture"' in html
    assert 'data-tab="quality-security"' in html

    # Verify standalone Structural Git Diff tab has been removed
    assert 'data-tab="diff"' not in html
    assert 'id="view-diff"' not in html


def test_source_code_retrieval_endpoint():
    """Verify GET /source retrieves actual source code content with line counts."""
    response = client.get("/source", params={"file_path": "services/user_service.py", "repository_id": "sample_repo"})
    assert response.status_code == 200
    data = response.json()
    assert data["file_path"] == "services/user_service.py"
    assert "content" in data
    assert data["line_count"] > 0
    assert data["language"] == "python"


def test_source_code_not_found():
    """Verify GET /source returns 404 for non-existent files."""
    response = client.get("/source", params={"file_path": "non_existent_file_999.py"})
    assert response.status_code == 404


def test_graph_summary_endpoint_extended():
    """Verify GET /graph/{repository_id} returns structured nodes, relationships, and metadata."""
    response = client.get("/graph/sample_repo", params={"limit": 50})
    assert response.status_code == 200
    data = response.json()
    assert data["repository_id"] == "sample_repo"
    assert "node_distribution" in data
    assert "relationship_distribution" in data
    assert "nodes" in data
    assert "relationships" in data
    assert "metadata" in data


def test_query_view_dom_elements_present():
    """Verify that index.html contains the necessary DOM elements for Codebase Query."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert 'id="view-query"' in html
    assert 'id="query-input"' in html
    assert 'id="btn-run-query"' in html
    assert 'id="query-results"' in html
    assert 'id="query-suggestions-list"' in html


def test_query_js_module_targets_results_container():
    """Verify frontend/js/query.js references query-results and exports renderQueryResponse."""
    with open("frontend/js/query.js", encoding="utf-8") as f:
        content = f.read()

    assert 'document.getElementById("query-results")' in content
    assert "export function renderQueryResponse" in content
    assert "renderQueryResponse(response, resultsContainer)" in content
    assert "answer-container" in content
    assert "answer-text" in content
    assert "validation-badge" in content
    assert "sources-list" in content
