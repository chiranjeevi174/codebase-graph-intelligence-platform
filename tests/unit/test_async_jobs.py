"""Unit tests for async PR analysis job infrastructure, models, repository, and queue."""

import pytest

from app.jobs.models import (
    PRAnalysisJob,
    PRCommentStatus,
    PRJobRequest,
    PRJobResult,
    PRJobStatus,
)
from app.jobs.repository import JobRepository
from app.jobs.service import JobService


def test_job_model_validation():
    """Test Pydantic job model validation and default values."""
    job = PRAnalysisJob(
        job_id="test_job_123",
        provider="github",
        repository="owner/repo",
        pr_number=42,
        base_sha="base123",
        head_sha="head456",
        status=PRJobStatus.QUEUED,
        comment_status=PRCommentStatus.PENDING,
    )
    assert job.job_id == "test_job_123"
    assert job.provider == "github"
    assert job.repository == "owner/repo"
    assert job.pr_number == 42
    assert job.status == PRJobStatus.QUEUED
    assert job.comment_status == PRCommentStatus.PENDING
    assert job.attempt == 1
    assert job.max_attempts == 3


def test_job_state_transitions():
    """Test valid job state transitions and status updates."""
    job = PRAnalysisJob(
        job_id="test_job_456",
        provider="gitlab",
        repository="group/project",
        pr_number=10,
        base_sha="base",
        head_sha="head",
        status=PRJobStatus.QUEUED,
    )
    assert job.status == PRJobStatus.QUEUED

    job.status = PRJobStatus.RUNNING
    job.started_at = "2026-10-02T12:00:00Z"
    assert job.status == PRJobStatus.RUNNING

    job.status = PRJobStatus.COMPLETED
    job.completed_at = "2026-10-02T12:01:00Z"
    job.comment_status = PRCommentStatus.POSTED
    assert job.status == PRJobStatus.COMPLETED
    assert job.comment_status == PRCommentStatus.POSTED


@pytest.mark.asyncio
async def test_job_idempotency_creation():
    """Test that identical requests return the same enqueued/completed job."""
    repo = JobRepository()
    service = JobService(repo=repo)

    req1 = PRJobRequest(
        provider="github",
        repository="test/repo",
        pr_number=99,
        base_ref="main",
        target_ref="feature-sha1",
        dry_run=True,
    )
    job1 = await service.submit_pr_job(req1)

    req2 = PRJobRequest(
        provider="github",
        repository="test/repo",
        pr_number=99,
        base_ref="main",
        target_ref="feature-sha1",
        dry_run=True,
    )
    job2 = await service.submit_pr_job(req2)

    assert job1.job_id == job2.job_id


def test_job_retry_policy():
    """Test job retry increment and attempt limits."""
    job = PRAnalysisJob(
        job_id="test_retry_job",
        provider="github",
        repository="test/repo",
        pr_number=5,
        base_sha="base",
        head_sha="head",
        status=PRJobStatus.RUNNING,
        attempt=1,
        max_attempts=3,
    )
    assert job.attempt < job.max_attempts
    job.attempt += 1
    assert job.attempt == 2
    job.attempt += 1
    assert job.attempt == 3
    assert job.attempt >= job.max_attempts


def test_comment_status_handling():
    """Test comment status distinct from job completion status."""
    result = PRJobResult(
        job_id="job_comment_test",
        status=PRJobStatus.COMPLETED,
        comment_status=PRCommentStatus.SKIPPED_DRY_RUN,
        analysis_run_id="run_101",
    )
    assert result.status == PRJobStatus.COMPLETED
    assert result.comment_status == PRCommentStatus.SKIPPED_DRY_RUN
