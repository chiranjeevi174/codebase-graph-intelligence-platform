"""Integration tests for async PR analysis job queue execution, worker dispatch, and API routes."""

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.jobs.models import PRJobRequest, PRJobStatus
from app.jobs.service import JobService
from app.jobs.worker import execute_pr_job_direct


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    app = create_app()
    return TestClient(app)


import time


@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_pr_job_lifecycle(client):
    """Integration test verifying async job creation, execution, state transition, and result retrieval."""
    unique_pr = int(time.time() * 1000) % 900000 + 100000
    payload = {
        "provider": "github",
        "repository": "sample_repo",
        "pr_number": unique_pr,
        "repo_path": "tests/fixtures/sample_repo",
        "base_ref": "HEAD~1",
        "target_ref": "HEAD",
        "dry_run": True,
        "max_hops": 3,
    }

    # 1. Post webhook/manual async job
    res = client.post("/analysis/pr", json=payload)
    assert res.status_code == 202
    job_data = res.json()
    job_id = job_data["job_id"]
    assert job_data["status"] == "QUEUED"

    # 2. Check status route
    status_res = client.get(f"/jobs/{job_id}")
    assert status_res.status_code == 200
    assert status_res.json()["job_id"] == job_id

    # 3. Direct worker execution
    exec_res = await execute_pr_job_direct(job_id)
    assert exec_res["status"] == "COMPLETED"

    # 4. Verify job completed status
    status_res_after = client.get(f"/jobs/{job_id}")
    assert status_res_after.status_code == 200
    job_completed = status_res_after.json()
    assert job_completed["status"] == "COMPLETED"

    # 5. Retrieve job result
    result_res = client.get(f"/jobs/{job_id}/result")
    assert result_res.status_code == 200
    report = result_res.json()
    assert report["provider"] == "github"
    assert "summary" in report


@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_pr_job_idempotency(client):
    """Integration test verifying idempotency returns existing job for identical payload."""
    unique_pr = int(time.time() * 1000) % 900000 + 200000
    payload = {
        "provider": "github",
        "repository": "sample_repo",
        "pr_number": unique_pr,
        "repo_path": "tests/fixtures/sample_repo",
        "base_ref": "HEAD~1",
        "target_ref": "HEAD",
        "dry_run": True,
    }

    res1 = client.post("/analysis/pr", json=payload)
    assert res1.status_code == 202
    job1 = res1.json()

    res2 = client.post("/analysis/pr", json=payload)
    assert res2.status_code == 202
    job2 = res2.json()

    assert job1["job_id"] == job2["job_id"]


from unittest.mock import patch


@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_pr_job_failure_handling(client):
    """Integration test verifying worker failure updates job status to FAILED."""
    service = JobService()
    req = PRJobRequest(
        provider="github",
        repository="invalid_repo_dir",
        pr_number=999,
        repo_path="invalid/path",
        base_ref="HEAD~1",
        target_ref="HEAD",
        dry_run=True,
    )
    job = await service.submit_pr_job(req)
    job.max_attempts = 1
    service.repo.update_job(job)

    with patch("app.pr.service.PRAnalysisService.analyze_pr", side_effect=RuntimeError("Graph database connectivity error")):
        exec_res = await execute_pr_job_direct(job.job_id)
        assert exec_res["status"] in ("FAILED", "DEAD_LETTER")

    # Check status
    updated_job = service.get_job(job.job_id)
    assert updated_job.status in (PRJobStatus.FAILED, PRJobStatus.DEAD_LETTER)
    assert updated_job.error is not None

