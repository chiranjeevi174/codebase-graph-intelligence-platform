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


@pytest.mark.asyncio
async def test_completed_job_not_silently_reused_on_new_submission():
    """Verify that a completed job is not silently reused for a subsequent analysis request."""
    repo = JobRepository()
    service = JobService(repo=repo)

    req = PRJobRequest(
        provider="github",
        repository="test/repo_reanalyze",
        pr_number=101,
        base_ref="main",
        target_ref="feature-sha2",
        dry_run=True,
    )
    job1 = await service.submit_pr_job(req)
    # Mark job1 as COMPLETED
    job1.status = PRJobStatus.COMPLETED
    repo.update_job(job1)

    # Submitting a fresh request must create a fresh job
    job2 = await service.submit_pr_job(req)
    assert job2.job_id != job1.job_id
    assert job2.status == PRJobStatus.QUEUED

    # Completed historical job remains available in repository
    old_job = repo.get_job(job1.job_id)
    assert old_job is not None
    assert old_job.status == PRJobStatus.COMPLETED


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


@pytest.mark.asyncio
async def test_stale_running_job_recovery():
    """Test that a stale job in RUNNING status is detected, marked FAILED, and a fresh job is submitted."""
    from datetime import UTC, datetime, timedelta
    from unittest.mock import AsyncMock

    repo = JobRepository()
    queue = AsyncMock()
    service = JobService(repo=repo, queue=queue)

    stale_started = (datetime.now(UTC) - timedelta(seconds=500)).isoformat()
    stale_job = PRAnalysisJob(
        job_id="test_stale_job_999",
        provider="github",
        repository="test/stale_repo",
        pr_number=77,
        base_sha="main",
        head_sha="feat_stale",
        status=PRJobStatus.RUNNING,
        started_at=stale_started,
        created_at=stale_started,
    )
    idempotency_key = "github:test/stale_repo:77:feat_stale"
    repo.create_job(stale_job, idempotency_key=idempotency_key)

    # Submit request with identical key
    req = PRJobRequest(
        provider="github",
        repository="test/stale_repo",
        pr_number=77,
        base_ref="main",
        target_ref="feat_stale",
        dry_run=True,
    )
    new_job = await service.submit_pr_job(req)

    # Verify stale job was marked FAILED
    updated_stale = repo.get_job("test_stale_job_999")
    assert updated_stale.status == PRJobStatus.FAILED
    assert "timed out" in updated_stale.error.lower()

    # Verify a new job was created and enqueued
    assert new_job.job_id != "test_stale_job_999"
    assert new_job.status == PRJobStatus.QUEUED
    assert queue.enqueue_pr_job.called


def test_find_api_flow_returns_unique_paths():
    """Verify GraphQueryManager.find_api_flow returns unique paths without NameError."""
    from unittest.mock import MagicMock

    from app.graph.graph_queries import GraphQueryManager

    mock_client = MagicMock()
    mock_client.execute_read.return_value = [
        {"path_nodes": [{"name": "A"}], "path_relationships": ["CALLS"]},
        {"path_nodes": [{"name": "A"}], "path_relationships": ["CALLS"]},  # duplicate
    ]

    gqm = GraphQueryManager(client=mock_client)
    res = gqm.find_api_flow(identifier="TestService", max_hops=2)
    assert len(res) == 1
    assert res[0]["path_nodes"][0]["name"] == "A"


def test_impact_analysis_request_include_explanation_flag():
    """Verify ImpactAnalysisRequest supports include_explanation=False."""
    from unittest.mock import MagicMock

    from app.analysis.impact_service import CodeImpactAnalysisService
    from app.models.entities import ImpactAnalysisRequest, ResolvedEntity

    req = ImpactAnalysisRequest(symbol="test_sym", include_explanation=False)
    assert req.include_explanation is False

    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = [
        ResolvedEntity(
            symbol_id="test_id", qualified_name="test_sym", name="test_sym", symbol_type="Function", file_path="test.py"
        )
    ]
    mock_queries = MagicMock()
    mock_queries.get_direct_relationships.return_value = []
    mock_queries.traverse_impact_paths.return_value = []
    mock_retriever = MagicMock()

    svc = CodeImpactAnalysisService(
        entity_resolver=mock_resolver,
        graph_query_manager=mock_queries,
        semantic_retriever=mock_retriever,
    )

    res = svc.analyze_impact(req)
    assert "Static graph impact analysis completed" in res.explanation
    # Semantic retriever and LLM must NOT be called when include_explanation=False
    mock_retriever.retrieve.assert_not_called()
