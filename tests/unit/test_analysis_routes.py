"""Unit tests for Analysis API routes including new Architecture and Quality/Security endpoints."""

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_architecture_analysis_endpoint():
    """Verify POST /analysis/architecture returns structured ArchitectureAnalysisResult."""
    payload = {
        "repository_id": "sample_repo",
        "level": "overview",
    }
    response = client.post("/analysis/architecture", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["repository_id"] == "sample_repo"
    assert "summary" in data
    assert "layers" in data
    assert "nodes" in data
    assert "edges" in data
    assert "entry_points" in data
    assert "explanation" in data
    assert data["summary"]["total_files"] > 0


def test_quality_security_analysis_endpoint():
    """Verify POST /analysis/quality-security returns structured QualitySecurityAnalysisResult."""
    payload = {
        "repository_id": "sample_repo",
        "categories": ["quality", "security"],
    }
    response = client.post("/analysis/quality-security", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["repository_id"] == "sample_repo"
    assert "summary" in data
    assert "findings" in data
    assert "explanation" in data
    assert data["summary"]["files_scanned"] > 0


def test_openapi_schema_removes_standalone_diff():
    """Verify OpenAPI schema does not expose /analysis/diff as a user-facing route."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    # New features must be present
    assert "/analysis/architecture" in paths
    assert "/analysis/quality-security" in paths

    # Standalone structural diff should not be in public schema
    assert "/analysis/diff" not in paths
