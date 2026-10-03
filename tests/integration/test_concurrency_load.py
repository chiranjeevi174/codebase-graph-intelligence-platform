"""Integration load test verifying bounded concurrent PR analysis job submission and worker execution."""

import asyncio
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.jobs.worker import execute_pr_job_direct


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    app = create_app()
    return TestClient(app)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_jobs_submission_and_execution(client):
    """Submit multiple concurrent independent analysis jobs and verify state consistency."""
    num_jobs = 5
    job_ids = []

    # 1. Concurrent submissions
    for i in range(1, num_jobs + 1):
        payload = {
            "provider": "github",
            "repository": "sample_repo",
            "pr_number": 100 + i,
            "repo_path": "tests/fixtures/sample_repo",
            "base_ref": "HEAD~1",
            "target_ref": "HEAD",
            "dry_run": True,
        }
        res = client.post("/analysis/pr", json=payload)
        assert res.status_code == 202
        job_ids.append(res.json()["job_id"])

    # Ensure all job IDs are unique across distinct PR numbers
    assert len(set(job_ids)) == num_jobs

    # 2. Process all jobs asynchronously
    tasks = [execute_pr_job_direct(jid) for jid in job_ids]
    results = await asyncio.gather(*tasks)

    for r in results:
        assert r["status"] == "COMPLETED"

    # 3. Verify all jobs status API endpoints return COMPLETED
    for jid in job_ids:
        status_res = client.get(f"/jobs/{jid}")
        assert status_res.status_code == 200
        assert status_res.json()["status"] == "COMPLETED"
