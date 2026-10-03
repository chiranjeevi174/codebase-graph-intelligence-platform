"""JobRepository persistence abstraction layer over Redis with in-memory fallback."""

import json
from typing import Any

from app.config.settings import Settings, get_settings
from app.jobs.models import PRAnalysisJob, PRCommentStatus, PRJobStatus
from app.pr.models import PRAnalysisResult
from app.utils.logger import logger

# Global in-memory storage fallback when Redis is offline
_MEMORY_JOBS: dict[str, PRAnalysisJob] = {}
_MEMORY_RESULTS: dict[str, PRAnalysisResult] = {}
_MEMORY_IDEMPOTENCY: dict[str, str] = {}
_MEMORY_DELIVERIES: set[str] = set()
_MEMORY_RUNS: dict[str, list[Any]] = {}


class JobRepository:
    """Provides storage, lookup, and TTL lifecycle management for PR analysis jobs."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _get_redis_client(self) -> Any:
        """Attempt to establish Redis client connection; returns None if Redis unavailable in dev/test."""
        try:
            import redis
            client: Any = redis.Redis.from_url(
                self.settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=self.settings.REDIS_TIMEOUT_SECONDS,
                socket_connect_timeout=self.settings.REDIS_TIMEOUT_SECONDS,
                retry_on_timeout=True,
            )
            client.ping()
            return client
        except Exception as e:
            if self.settings.ENVIRONMENT == "production":
                raise RuntimeError(f"[JobRepository] Production environment requires operational Redis at '{self.settings.REDIS_URL}': {e}")
            return None

    def record_delivery(self, provider: str, delivery_id: str) -> None:
        """Record processed webhook delivery ID to prevent duplicate processing."""
        if not delivery_id:
            return
        key = f"delivery:{provider.lower()}:{delivery_id}"
        r = self._get_redis_client()
        if r:
            try:
                r.set(key, "1", ex=self.settings.IDEMPOTENCY_TTL_SECONDS)
                return
            except Exception as e:
                logger.warning(f"[JobRepository] Redis error on record_delivery: {e}")

        _MEMORY_DELIVERIES.add(key)

    def is_duplicate_delivery(self, provider: str, delivery_id: str) -> bool:
        """Check if delivery ID has already been received and processed."""
        if not delivery_id:
            return False
        key = f"delivery:{provider.lower()}:{delivery_id}"
        r = self._get_redis_client()
        if r:
            try:
                return bool(r.exists(key))
            except Exception as e:
                logger.warning(f"[JobRepository] Redis error on is_duplicate_delivery: {e}")

        return key in _MEMORY_DELIVERIES

    def save_analysis_run(self, run: Any) -> None:
        """Save a PRAnalysisRun historical record."""
        key = f"pr_history:{run.provider.lower()}:{run.repository.lower()}:{run.pr_number}"
        run_json = run.model_dump_json()

        r = self._get_redis_client()
        if r:
            try:
                r.lpush(key, run_json)
                r.ltrim(key, 0, 99)
                r.expire(key, self.settings.JOB_TTL_SECONDS * 7)
                return
            except Exception as e:
                logger.warning(f"[JobRepository] Redis error on save_analysis_run: {e}")

        if key not in _MEMORY_RUNS:
            _MEMORY_RUNS[key] = []
        # Prepend latest run
        _MEMORY_RUNS[key].insert(0, run)
        _MEMORY_RUNS[key] = _MEMORY_RUNS[key][:100]

    def get_pr_history(self, provider: str, repository: str, pr_number: int, limit: int = 20) -> list[Any]:
        """Fetch historical analysis runs for specified PR."""
        from app.jobs.models import PRAnalysisRun

        key = f"pr_history:{provider.lower()}:{repository.lower()}:{pr_number}"
        history: list[PRAnalysisRun] = []

        r = self._get_redis_client()
        if r:
            try:
                items = r.lrange(key, 0, limit - 1)
                for raw in items:
                    history.append(PRAnalysisRun.model_validate_json(raw))
                if history:
                    return history
            except Exception as e:
                logger.warning(f"[JobRepository] Redis error on get_pr_history: {e}")

        mem_items = _MEMORY_RUNS.get(key, [])
        return mem_items[:limit]

    def create_job(self, job: PRAnalysisJob, idempotency_key: str | None = None) -> PRAnalysisJob:
        """Persist a new job and record idempotency key."""
        r = self._get_redis_client()
        job_json = job.model_dump_json()

        if r:
            try:
                r.set(f"job:{job.job_id}", job_json, ex=self.settings.JOB_TTL_SECONDS)
                if idempotency_key:
                    r.set(f"idempotency:{idempotency_key}", job.job_id, ex=self.settings.IDEMPOTENCY_TTL_SECONDS)
                logger.info(f"[JobRepository] Persisted job '{job.job_id}' to Redis.")
                return job
            except Exception as e:
                logger.warning(f"[JobRepository] Redis error on create_job: {e}. Falling back to memory.")

        _MEMORY_JOBS[job.job_id] = job
        if idempotency_key:
            _MEMORY_IDEMPOTENCY[idempotency_key] = job.job_id
        return job

    def get_job(self, job_id: str) -> PRAnalysisJob | None:
        """Fetch job metadata by job ID."""
        r = self._get_redis_client()
        if r:
            try:
                val = r.get(f"job:{job_id}")
                if val:
                    return PRAnalysisJob.model_validate_json(val)
            except Exception as e:
                logger.warning(f"[JobRepository] Redis error on get_job: {e}")

        return _MEMORY_JOBS.get(job_id)

    def update_job(self, job: PRAnalysisJob) -> PRAnalysisJob:
        """Update existing job status and timestamp fields."""
        r = self._get_redis_client()
        job_json = job.model_dump_json()

        if r:
            try:
                r.set(f"job:{job.job_id}", job_json, ex=self.settings.JOB_TTL_SECONDS)
                return job
            except Exception as e:
                logger.warning(f"[JobRepository] Redis error on update_job: {e}")

        _MEMORY_JOBS[job.job_id] = job
        return job

    def save_job_result(self, job_id: str, result: PRAnalysisResult) -> None:
        """Persist completed PRAnalysisResult report."""
        r = self._get_redis_client()
        res_json = result.model_dump_json()

        if r:
            try:
                r.set(f"result:{job_id}", res_json, ex=self.settings.JOB_TTL_SECONDS)
                return
            except Exception as e:
                logger.warning(f"[JobRepository] Redis error on save_job_result: {e}")

        _MEMORY_RESULTS[job_id] = result

    def get_job_result(self, job_id: str) -> PRAnalysisResult | None:
        """Fetch completed PRAnalysisResult report for a job."""
        r = self._get_redis_client()
        if r:
            try:
                val = r.get(f"result:{job_id}")
                if val:
                    return PRAnalysisResult.model_validate_json(val)
            except Exception as e:
                logger.warning(f"[JobRepository] Redis error on get_job_result: {e}")

        return _MEMORY_RESULTS.get(job_id)

    def find_existing_job_by_key(self, idempotency_key: str) -> PRAnalysisJob | None:
        """Check if an identical active/completed job exists for given key."""
        r = self._get_redis_client()
        job_id = None

        if r:
            try:
                job_id = r.get(f"idempotency:{idempotency_key}")
            except Exception:
                pass

        if not job_id:
            job_id = _MEMORY_IDEMPOTENCY.get(idempotency_key)

        if job_id:
            return self.get_job(job_id)
        return None

    def list_jobs(
        self,
        repository: str | None = None,
        provider: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[PRAnalysisJob]:
        """List bounded historical jobs with optional filtering."""
        all_jobs: list[PRAnalysisJob] = []

        r = self._get_redis_client()
        if r:
            try:
                keys = r.keys("job:*")[:limit * 2]
                for k in keys:
                    val = r.get(k)
                    if val:
                        all_jobs.append(PRAnalysisJob.model_validate_json(val))
            except Exception as e:
                logger.warning(f"[JobRepository] Redis error on list_jobs: {e}")

        if not all_jobs:
            all_jobs = list(_MEMORY_JOBS.values())

        # Filter
        filtered = []
        for j in all_jobs:
            if repository and j.repository != repository and j.repository.split("/")[-1] != repository:
                continue
            if provider and j.provider != provider:
                continue
            if status and j.status.value != status and j.status != status:
                continue
            filtered.append(j)

        return filtered[:limit]

