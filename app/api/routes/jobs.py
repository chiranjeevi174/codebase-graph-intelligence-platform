"""Async PR Analysis Job status, result, events, and listing API routes."""

import asyncio

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.jobs.models import PRAnalysisJob, PRJobStatus
from app.jobs.service import JobService

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("", response_model=list[PRAnalysisJob])
def list_jobs(
    repository: str | None = Query(None, description="Optional repository name filter"),
    provider: str | None = Query(None, description="Optional provider filter e.g. github, gitlab"),
    status: str | None = Query(None, description="Optional job status filter e.g. QUEUED, COMPLETED, FAILED"),
    limit: int = Query(50, description="Maximum number of historical jobs to return"),
):
    """List bounded historical PR analysis jobs with optional filters."""
    service = JobService()
    return service.list_jobs(repository=repository, provider=provider, status=status, limit=limit)


@router.get("/{job_id}", response_model=PRAnalysisJob)
def get_job_status(job_id: str):
    """Retrieve async PR analysis job lifecycle metadata and status."""
    service = JobService()
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


@router.get("/{job_id}/events")
async def job_events_stream(job_id: str):
    """Server-Sent Events (SSE) streaming endpoint for real-time job state transitions."""
    service = JobService()
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    async def event_generator():
        for _ in range(60):
            current_job = service.get_job(job_id)
            if not current_job:
                break

            payload = current_job.model_dump_json()
            yield f"data: {payload}\n\n"

            if current_job.status in (
                PRJobStatus.COMPLETED,
                PRJobStatus.FAILED,
                PRJobStatus.DEAD_LETTER,
                PRJobStatus.CANCELLED,
            ):
                break

            await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{job_id}/result")
def get_job_result(job_id: str):
    """Retrieve completed PR Analysis Report result for specified job ID."""
    service = JobService()
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    if job.status == PRJobStatus.FAILED:
        return {
            "job_id": job_id,
            "status": "FAILED",
            "error": job.error or "Analysis failed",
            "comment_status": job.comment_status.value,
        }

    if job.status in (PRJobStatus.QUEUED, PRJobStatus.RUNNING):
        return {
            "job_id": job_id,
            "status": job.status.value,
            "message": "PR analysis job is currently processing.",
        }

    result = service.get_job_result(job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Result report for completed job '{job_id}' not found.")

    return result


@router.post("/{job_id}/retry", response_model=PRAnalysisJob)
async def retry_job(job_id: str):
    """Manually retry a FAILED or DEAD_LETTER PR analysis job."""
    service = JobService()
    try:
        return await service.retry_job(job_id)
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:  # noqa: BLE001 # FastAPI 500 error boundary
        raise HTTPException(status_code=500, detail=f"Failed to retry job: {e}")
