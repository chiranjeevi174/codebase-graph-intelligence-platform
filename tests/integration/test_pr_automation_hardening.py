"""Integration tests for PR automation hardening, webhooks, duplicate delivery, and history."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.api.main import create_app
from app.jobs.models import PRJobRequest, PRJobStatus
from app.jobs.repository import JobRepository
from app.jobs.service import JobService
from app.jobs.worker import execute_pr_job_direct


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    app = create_app()
    return TestClient(app)


import uuid


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_filtering_and_deduplication(client):
    """Test webhook action policy filtering and duplicate delivery rejection."""
    deliv1 = f"delivery_uuid_{uuid.uuid4().hex[:8]}"
    headers = {"X-GitHub-Delivery": deliv1, "X-GitHub-Event": "pull_request"}
    
    # 1. Closed event action -> ignored per policy
    closed_payload = {
        "action": "closed",
        "number": 10,
        "pull_request": {"number": 10, "title": "Closed PR", "head": {"sha": "sha_1"}, "base": {"sha": "sha_0"}},
        "repository": {"full_name": "sample/repo", "name": "repo"},
    }
    res_closed = client.post("/webhooks/github", json=closed_payload, headers=headers)
    assert res_closed.status_code == 202
    assert res_closed.json()["status"] == "SKIPPED_POLICY"

    # 2. Duplicate delivery ID check
    res_dup = client.post("/webhooks/github", json=closed_payload, headers=headers)
    assert res_dup.status_code == 202
    assert res_dup.json()["status"] == "SKIPPED_DUPLICATE_DELIVERY"

    # 3. Valid synchronize action with fresh delivery ID
    deliv2 = f"delivery_uuid_{uuid.uuid4().hex[:8]}"
    sync_headers = {"X-GitHub-Delivery": deliv2, "X-GitHub-Event": "pull_request"}
    sync_payload = {
        "action": "synchronize",
        "number": 10,
        "pull_request": {"number": 10, "title": "Sync PR", "head": {"sha": "sha_2"}, "base": {"sha": "sha_0"}},
        "repository": {"full_name": "sample/repo", "name": "repo"},
    }
    res_sync = client.post("/webhooks/github", json=sync_payload, headers=sync_headers)
    assert res_sync.status_code == 202
    assert res_sync.json()["status"] == "QUEUED"


import time


@pytest.mark.integration
@pytest.mark.asyncio
async def test_worker_observability_and_pr_history(client):
    """Test worker populates worker_id, duration_ms, and records PR history."""
    unique_pr = int(time.time() * 1000) % 900000 + 300000
    payload = {
        "provider": "github",
        "repository": "sample_repo",
        "pr_number": unique_pr,
        "repo_path": "tests/fixtures/sample_repo",
        "base_ref": "HEAD~1",
        "target_ref": "HEAD",
        "dry_run": True,
    }

    res = client.post("/analysis/pr", json=payload)
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    # Execute job
    exec_res = await execute_pr_job_direct(job_id)
    assert exec_res["status"] == "COMPLETED"

    # Verify job status & worker metadata
    job_res = client.get(f"/jobs/{job_id}")
    assert job_res.status_code == 200
    job_data = job_res.json()
    assert job_data["worker_id"] is not None
    assert job_data["duration_ms"] is not None
    assert job_data["status"] == "COMPLETED"

    # Verify PR history
    hist_res = client.get(f"/analysis/pr/github/sample_repo/{unique_pr}/history")
    assert hist_res.status_code == 200
    runs = hist_res.json()
    assert len(runs) >= 1
    assert runs[0]["job_id"] == job_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_manual_retry_endpoint(client):
    """Test manual retry API endpoint POST /jobs/{job_id}/retry."""
    service = JobService()
    job = await service.submit_pr_job(
        PRJobRequest(
            provider="github",
            repository="sample_repo",
            pr_number=55,
            dry_run=True,
        )
    )

    # Set status to FAILED
    job.status = PRJobStatus.FAILED
    job.error = "Test failure"
    service.repo.update_job(job)

    # Call POST /jobs/{job_id}/retry
    res_retry = client.post(f"/jobs/{job.job_id}/retry")
    assert res_retry.status_code == 200
    retried_job = res_retry.json()
    assert retried_job["status"] == "QUEUED"
    assert retried_job["error"] is None
