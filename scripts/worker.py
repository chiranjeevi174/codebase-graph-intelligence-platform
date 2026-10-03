#!/usr/bin/env python3
"""ARQ Worker Entry Point for executing background PR analysis jobs."""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arq.connections import RedisSettings
from app.config.settings import get_settings
from app.jobs.worker import perform_pr_analysis_job
from app.utils.logger import logger

settings = get_settings()


async def startup(ctx: dict):
    """Validate connectivity and initialize worker runtime context."""
    logger.info(f"[WorkerLifecycle] Initializing worker startup checks on Redis at '{settings.REDIS_URL}'...")
    from app.jobs.repository import JobRepository
    repo = JobRepository(settings=settings)
    client = repo._get_redis_client()
    if client is None and settings.ENVIRONMENT == "production":
        raise RuntimeError("[WorkerLifecycle] Failed to verify Redis connection during production worker startup.")
    logger.info("[WorkerLifecycle:startup_complete] Worker startup validation completed successfully.")


async def shutdown(ctx: dict):
    """Graceful worker shutdown handling."""
    logger.info("[WorkerLifecycle:shutdown_signal] Worker received shutdown signal. Releasing resources...")


class WorkerSettings:
    """ARQ Worker Configuration Class."""

    functions = [perform_pr_analysis_job]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = settings.WORKER_MAX_JOBS
    poll_delay = 0.5
    job_timeout = settings.WORKER_JOB_TIMEOUT
    max_tries = settings.WORKER_MAX_TRIES
    on_startup = startup
    on_shutdown = shutdown


if __name__ == "__main__":
    logger.info(f"Starting ARQ PR Analysis Worker process (Environment: {settings.ENVIRONMENT}) connecting to Redis at '{settings.REDIS_URL}'...")
    from arq.worker import run_worker
    run_worker(WorkerSettings)
