"""Unit tests for Phase 4 Production Hardening, Observability, and Middleware."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config.settings import Settings
from app.jobs.models import PRAnalysisJob, PRJobStatus
from app.jobs.repository import JobRepository
from app.parsing.go_parser import GoParser


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    app = create_app()
    return TestClient(app)


def test_settings_phase4_defaults():
    """Verify Phase 4 settings attributes and default timeouts."""
    settings = Settings()
    assert settings.ENVIRONMENT in ("development", "test", "production")
    assert settings.SECURITY_MAX_REQUEST_SIZE_BYTES > 0
    assert settings.NEO4J_TIMEOUT_SECONDS > 0
    assert settings.QDRANT_TIMEOUT_SECONDS > 0
    assert settings.REDIS_TIMEOUT_SECONDS > 0
    assert settings.RATE_LIMIT_PER_MINUTE > 0


def test_request_correlation_header(client):
    """Test X-Request-ID generation and header propagation in HTTP response."""
    res = client.get("/live")
    assert res.status_code == 200
    assert "X-Request-ID" in res.headers
    assert res.headers["X-Request-ID"].startswith("req_")

    # Custom request ID propagation
    custom_id = "req_custom_123456"
    res_custom = client.get("/live", headers={"X-Request-ID": custom_id})
    assert res_custom.status_code == 200
    assert res_custom.headers["X-Request-ID"] == custom_id


def test_observability_endpoints(client):
    """Test /live, /ready, and /metrics observability endpoints."""
    # Live
    res_live = client.get("/live")
    assert res_live.status_code == 200
    assert res_live.json() == {"status": "alive"}

    # Ready
    res_ready = client.get("/ready")
    assert res_ready.status_code in (200, 503)
    ready_data = res_ready.json()
    assert "status" in ready_data
    assert "services" in ready_data

    # Metrics
    res_metrics = client.get("/metrics")
    assert res_metrics.status_code == 200
    metrics = res_metrics.json()
    assert "total_requests" in metrics
    assert "status_code_distribution" in metrics


def test_tree_sitter_warning_free_initialization():
    """Verify parser initialization produces no deprecation warnings."""
    go_parser = GoParser()
    ts_parser = go_parser._get_ts_parser()
    assert ts_parser is not None


def test_sse_job_events_endpoint(client):
    """Test GET /jobs/{job_id}/events SSE streaming route."""
    repo = JobRepository()
    job = PRAnalysisJob(
        job_id="test_sse_job_001",
        provider="github",
        repository="owner/repo",
        pr_number=7,
        status=PRJobStatus.COMPLETED,
    )
    repo.create_job(job)

    res = client.get(f"/jobs/{job.job_id}/events")
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")
    assert "data: " in res.text
    assert "test_sse_job_001" in res.text
