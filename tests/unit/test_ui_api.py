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
    assert "Developer UI" in response.text or "<!DOCTYPE html>" in response.text


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
