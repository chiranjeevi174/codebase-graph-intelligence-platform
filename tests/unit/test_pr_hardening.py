"""Unit tests for Phase 3.3-D PR automation hardening components."""

import pytest
from app.api.routes.webhooks import normalize_action
from app.jobs.models import (
    PRAction,
    PRAnalysisJob,
    PRAnalysisRun,
    PRCommentStatus,
    PRJobStatus,
)
from app.jobs.repository import JobRepository
from app.jobs.service import JobService


def test_action_normalization():
    """Test raw provider string to PRAction enum mapping."""
    assert normalize_action("opened") == PRAction.OPENED
    assert normalize_action("open") == PRAction.OPENED
    assert normalize_action("synchronize") == PRAction.UPDATED
    assert normalize_action("update") == PRAction.UPDATED
    assert normalize_action("reopened") == PRAction.REOPENED
    assert normalize_action("closed") == PRAction.CLOSED
    assert normalize_action("unknown_action") == PRAction.UNKNOWN


def test_duplicate_delivery_deduplication():
    """Test webhook delivery ID recording and lookup."""
    repo = JobRepository()
    delivery_id = "delivery_test_999"

    assert repo.is_duplicate_delivery("github", delivery_id) is False
    repo.record_delivery("github", delivery_id)
    assert repo.is_duplicate_delivery("github", delivery_id) is True


def test_analysis_run_model_and_pr_history():
    """Test saving and retrieving PRAnalysisRun records."""
    repo = JobRepository()
    run1 = PRAnalysisRun(
        analysis_run_id="run_001",
        job_id="job_001",
        provider="github",
        repository="owner/test_repo",
        pr_number=101,
        base_sha="sha_base",
        head_sha="sha_head_1",
        status=PRJobStatus.COMPLETED,
        created_at="2026-10-02T10:00:00Z",
        comment_status=PRCommentStatus.POSTED,
    )
    repo.save_analysis_run(run1)

    history = repo.get_pr_history("github", "owner/test_repo", 101)
    assert len(history) >= 1
    latest = history[0]
    assert latest.analysis_run_id == "run_001"
    assert latest.head_sha == "sha_head_1"


def test_dead_letter_and_retry_behavior():
    """Test manual job retry resets FAILED / DEAD_LETTER jobs to QUEUED."""
    repo = JobRepository()
    service = JobService(repo=repo)

    job = PRAnalysisJob(
        job_id="test_dead_job",
        provider="github",
        repository="owner/repo",
        pr_number=5,
        status=PRJobStatus.DEAD_LETTER,
        error="Retries exhausted",
        attempt=3,
        max_attempts=3,
    )
    repo.create_job(job)

    retried_job = service.retry_job("test_dead_job")
    assert retried_job.status == PRJobStatus.QUEUED
    assert retried_job.attempt == 1
    assert retried_job.error is None
