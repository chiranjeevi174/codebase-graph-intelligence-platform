"""Async PR Job Queue interface using ARQ / Redis with in-memory fallback."""

import asyncio
from typing import Any

from app.config.settings import Settings, get_settings
from app.jobs.models import PRAnalysisJob
from app.utils.logger import logger


class PRJobQueue:
    """Queue client for enqueueing PR analysis jobs to Redis / ARQ."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    async def enqueue_pr_job(self, job: PRAnalysisJob) -> bool:
        """Enqueue job to ARQ redis queue or background event loop."""
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            redis_settings = RedisSettings.from_dsn(self.settings.REDIS_URL)
            arq_pool = await create_pool(redis_settings)
            await arq_pool.enqueue_job("perform_pr_analysis_job", job.model_dump())
            await arq_pool.close()
            logger.info(f"[PRJobQueue:job_queued] Enqueued job '{job.job_id}' to ARQ Redis queue.")
            return True
        except Exception as e:
            logger.warning(f"[PRJobQueue] Redis/ARQ enqueue warning: {e}. Executing via fallback task.")
            # Execute in background asyncio task for non-blocking local runs
            from app.jobs.worker import execute_pr_job_direct
            asyncio.create_task(execute_pr_job_direct(job.job_id))
            return True
