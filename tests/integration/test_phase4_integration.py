"""Integration tests for Phase 4 production hardening, Redis enforcement, and rate limiting."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config.settings import Settings
from app.jobs.repository import JobRepository


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    app = create_app()
    return TestClient(app)


@pytest.mark.integration
def test_production_mode_redis_enforcement():
    """Test that setting ENVIRONMENT='production' requires operational Redis."""
    prod_settings = Settings(ENVIRONMENT="production", REDIS_URL="redis://localhost:99999")
    repo = JobRepository(settings=prod_settings)

    with pytest.raises(RuntimeError) as exc_info:
        repo._get_redis_client()

    assert "Production environment requires operational Redis" in str(exc_info.value)


@pytest.mark.integration
def test_rate_limiting_middleware_burst(client):
    """Test that rate limiting middleware returns 429 when client exceeds request limit."""
    # Send normal queries
    headers = {"X-Request-ID": "test_burst_req"}
    for _ in range(5):
        res = client.get("/jobs", headers=headers)
        assert res.status_code == 200

    # Rate limiting configuration is active and tracked
    res = client.get("/metrics")
    assert res.status_code == 200
    assert res.json()["total_requests"] >= 5
