"""JobService orchestrating job submission, idempotency, queue dispatch, and status inspection."""

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any

from app.config.settings import Settings, get_settings
from app.jobs.models import (
    PRAnalysisJob,
    PRCommentStatus,
    PRJobRequest,
    PRJobStatus,
)
from app.jobs.queue import PRJobQueue
from app.jobs.repository import JobRepository
from app.jobs.worker import execute_pr_job_direct
from app.pr.models import PRAnalysisResult
from app.utils.logger import logger


class JobService:
    """Orchestrates job lifecycle submission, idempotency checks, and status API lookups."""

    def __init__(self, repo: JobRepository | None = None, queue: PRJobQueue | None = None, settings: Settings | None = None):
        self.repo = repo or JobRepository()
        self.queue = queue or PRJobQueue()
        self.settings = settings or get_settings()

    async def submit_pr_job(self, request: PRJobRequest) -> PRAnalysisJob:
        """Submit a PR analysis job for async background worker processing."""
        repo_clean = request.repository.strip()
        base_ref = request.base_ref.strip()
        target_ref = request.target_ref.strip()
        provider = request.provider.strip().lower()

        # Idempotency Key
        idempotency_key = f"{provider}:{repo_clean}:{request.pr_number}:{target_ref}"

        # Check existing job
        existing = self.repo.find_existing_job_by_key(idempotency_key)
        if existing and existing.status in (PRJobStatus.QUEUED, PRJobStatus.RUNNING, PRJobStatus.COMPLETED):
            logger.info(f"[JobService] Reusing existing job '{existing.job_id}' for idempotency key '{idempotency_key}' (Status: {existing.status.value}).")
            return existing

        # Generate deterministic job ID
        key_hash = hashlib.md5(f"{idempotency_key}:{datetime.now(timezone.utc).timestamp()}".encode("utf-8")).hexdigest()[:10]
        job_id = f"pr_job_{key_hash}"
        now_iso = datetime.now(timezone.utc).isoformat()

        job = PRAnalysisJob(
            job_id=job_id,
            provider=provider,
            repository=repo_clean,
            pr_number=request.pr_number,
            base_sha=base_ref,
            head_sha=target_ref,
            repo_path=request.repo_path,
            dry_run=request.dry_run,
            max_hops=request.max_hops,
            status=PRJobStatus.QUEUED,
            comment_status=PRCommentStatus.PENDING,
            attempt=1,
            max_attempts=3,
            created_at=now_iso,
        )

        # Persist job
        self.repo.create_job(job, idempotency_key=idempotency_key)

        # Enqueue job to worker queue asynchronously
        await self.queue.enqueue_pr_job(job)
        logger.info(f"[JobService:job_created] Created and enqueued job '{job.job_id}' for {repo_clean} #{request.pr_number}.")

        # If wait=True explicitly requested, execute or poll synchronously
        if request.wait:
            await execute_pr_job_direct(job.job_id)
            job = self.repo.get_job(job.job_id) or job

        return job

    def get_job(self, job_id: str) -> PRAnalysisJob | None:
        """Fetch job status metadata by job ID."""
        return self.repo.get_job(job_id)

    def get_job_result(self, job_id: str) -> PRAnalysisResult | None:
        """Fetch completed result report for job ID."""
        return self.repo.get_job_result(job_id)

    def list_jobs(self, repository: str | None = None, provider: str | None = None, status: str | None = None, limit: int = 50) -> list[PRAnalysisJob]:
        """List bounded historical jobs with filtering."""
        return self.repo.list_jobs(repository=repository, provider=provider, status=status, limit=limit)

    async def retry_job(self, job_id: str) -> PRAnalysisJob:
        """Retry a failed or dead-letter job."""
        job = self.repo.get_job(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        if job.status not in (PRJobStatus.FAILED, PRJobStatus.DEAD_LETTER):
            raise ValueError(f"Job '{job_id}' in state '{job.status.value}' cannot be retried. Only FAILED or DEAD_LETTER jobs can be retried.")

        job.status = PRJobStatus.QUEUED
        job.attempt = 1
        job.error = None
        job.failure_type = None
        job.started_at = None
        job.completed_at = None

        self.repo.update_job(job)

        await self.queue.enqueue_pr_job(job)

        logger.info(f"[JobService:job_retried] Manually retried job '{job.job_id}'.")
        return job

