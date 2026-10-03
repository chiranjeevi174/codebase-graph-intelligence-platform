import os
import socket
import time
from datetime import datetime, timezone
from typing import Any

from app.jobs.models import PRAnalysisJob, PRAnalysisRun, PRCommentStatus, PRJobStatus
from app.jobs.repository import JobRepository
from app.pr.models import PRAnalysisRequest
from app.pr.service import PRAnalysisService
from app.utils.logger import logger


def get_worker_id() -> str:
    """Generate a stable identifier for the executing worker process."""
    try:
        host = socket.gethostname().split(".")[0]
        pid = os.getpid()
        return f"worker_{host}_{pid}"
    except Exception:
        return "worker_local_1"


async def perform_pr_analysis_job(ctx: dict[str, Any], job_dict: dict[str, Any]) -> dict[str, Any]:
    """ARQ worker task function processing an enqueued PR analysis job."""
    job_id = job_dict.get("job_id") or "unknown"
    return await execute_pr_job_direct(job_id)


async def execute_pr_job_direct(job_id: str) -> dict[str, Any]:
    """Direct execution helper for processing a job asynchronously in a worker or task context."""
    start_time = time.time()
    worker_id = get_worker_id()
    repo_db = JobRepository()
    job = repo_db.get_job(job_id)

    if not job:
        logger.error(f"[Worker] Job '{job_id}' not found in repository.")
        return {"status": "FAILED", "error": "Job not found"}

    now_iso = datetime.now(timezone.utc).isoformat()
    job.status = PRJobStatus.RUNNING
    job.started_at = now_iso
    job.worker_id = worker_id
    repo_db.update_job(job)

    logger.info(f"[Worker:job_started] Worker '{worker_id}' processing job '{job.job_id}' for {job.repository} #{job.pr_number} (Attempt {job.attempt}/{job.max_attempts})")

    try:
        # Delegate to PRAnalysisService
        pr_service = PRAnalysisService()
        req = PRAnalysisRequest(
            provider=job.provider,
            repository=job.repository,
            pr_number=job.pr_number,
            repo_path=job.repo_path,
            base_ref=job.base_sha,
            target_ref=job.head_sha,
            dry_run=job.dry_run,
            max_hops=job.max_hops,
        )

        result = pr_service.analyze_pr(req)

        # Save completed result report
        repo_db.save_job_result(job.job_id, result)

        # Update job lifecycle & observability
        end_time = time.time()
        end_iso = datetime.now(timezone.utc).isoformat()
        job.status = PRJobStatus.COMPLETED
        job.completed_at = end_iso
        job.duration_ms = round((end_time - start_time) * 1000, 2)
        job.analysis_run_id = result.analysis_run_id
        job.result_reference = f"/jobs/{job.job_id}/result"

        if result.dry_run:
            job.comment_status = PRCommentStatus.SKIPPED_DRY_RUN
        elif result.comment:
            job.comment_status = PRCommentStatus.POSTED
        else:
            job.comment_status = PRCommentStatus.FAILED

        repo_db.update_job(job)

        # Persist historical PRAnalysisRun
        run_record = PRAnalysisRun(
            analysis_run_id=result.analysis_run_id,
            job_id=job.job_id,
            provider=job.provider,
            repository=job.repository,
            pr_number=job.pr_number,
            base_sha=result.base_sha,
            head_sha=result.head_sha,
            status=PRJobStatus.COMPLETED,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=end_iso,
            result_reference=job.result_reference,
            comment_status=job.comment_status,
        )
        repo_db.save_analysis_run(run_record)

        logger.info(f"[Worker:job_completed] Job '{job.job_id}' completed by '{worker_id}' in {job.duration_ms}ms.")
        return {"status": "COMPLETED", "job_id": job.job_id, "analysis_run_id": result.analysis_run_id}

    except Exception as e:
        err_msg = str(e)
        end_time = time.time()
        end_iso = datetime.now(timezone.utc).isoformat()
        job.duration_ms = round((end_time - start_time) * 1000, 2)

        # Classify failure type
        permanent_keywords = ["not found", "invalid repository", "unauthorized", "invalid/path", "invalid signature"]
        is_permanent = any(kw in err_msg.lower() for kw in permanent_keywords)
        job.failure_type = "permanent" if is_permanent else "transient"

        logger.error(f"[Worker:job_failed] Error in job '{job.job_id}' ({job.failure_type}): {err_msg}")

        if not is_permanent and job.attempt < job.max_attempts:
            job.attempt += 1
            job.retry_count += 1
            job.status = PRJobStatus.QUEUED
            logger.info(f"[Worker:job_retry] Retrying job '{job.job_id}' (Attempt {job.attempt}/{job.max_attempts}).")
        else:
            job.status = PRJobStatus.DEAD_LETTER if job.attempt >= job.max_attempts else PRJobStatus.FAILED
            job.completed_at = end_iso
            job.error = f"Job failed ({job.failure_type}): {err_msg[:250]}"
            job.comment_status = PRCommentStatus.FAILED

        repo_db.update_job(job)
        return {"status": job.status.value, "job_id": job.job_id, "error": job.error}

