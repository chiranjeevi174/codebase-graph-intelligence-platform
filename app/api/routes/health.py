"""Health, Liveness, Readiness, and Metrics observability endpoints."""

from fastapi import APIRouter, Response, status

from app.api.middleware import metrics_registry
from app.config.settings import get_settings
from app.embeddings.qdrant_store import QdrantStore
from app.graph.neo4j_client import Neo4jClient

router = APIRouter(tags=["Health"])


@router.get("/live", status_code=status.HTTP_200_OK)
def liveness_check():
    """Liveness probe returning HTTP 200 OK if application process is running."""
    return {"status": "alive"}


@router.get("/ready")
def readiness_check(response: Response):
    """Readiness probe verifying operational connectivity of downstream databases and queues."""
    settings = get_settings()

    neo4j_ready = False
    try:
        client = Neo4jClient(settings=settings)
        neo4j_ready = client.verify_connectivity()
    except Exception:  # noqa: BLE001 # Health probe service connectivity fallback
        neo4j_ready = False

    qdrant_ready = False
    try:
        qdrant = QdrantStore(settings=settings)
        qdrant.ensure_collection()
        qdrant_ready = True
    except Exception:  # noqa: BLE001 # Health probe service connectivity fallback
        qdrant_ready = False

    redis_ready = False
    try:
        import redis

        r = redis.Redis.from_url(
            settings.REDIS_URL, decode_responses=True, socket_timeout=settings.REDIS_TIMEOUT_SECONDS
        )
        redis_ready = bool(r.ping())
        r.close()
    except Exception:  # noqa: BLE001 # Health probe service connectivity fallback
        redis_ready = False

    is_production = settings.ENVIRONMENT == "production"
    is_ready = neo4j_ready and qdrant_ready and (redis_ready if is_production else True)

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "unready",
        "environment": settings.ENVIRONMENT,
        "services": {
            "neo4j": "ready" if neo4j_ready else "unready",
            "qdrant": "ready" if qdrant_ready else "unready",
            "redis": "ready" if redis_ready else "unready",
        },
    }


@router.get("/metrics")
def get_metrics():
    """Returns application runtime request, error, latency, and endpoint metrics summary."""
    return metrics_registry.get_summary()


@router.get("/health")
def health_check():
    """Returns detailed diagnostic system status, active LLM provider, and connectivity metrics."""
    settings = get_settings()

    neo4j_status = "unknown"
    try:
        client = Neo4jClient(settings=settings)
        if client.verify_connectivity():
            neo4j_status = "connected"
    except Exception as e:  # noqa: BLE001 # Health probe service diagnostic fallback
        neo4j_status = f"disconnected: {e}"

    qdrant_status = "unknown"
    try:
        qdrant = QdrantStore(settings=settings)
        qdrant.ensure_collection()
        qdrant_status = "connected"
    except Exception as e:  # noqa: BLE001 # Health probe service diagnostic fallback
        qdrant_status = f"disconnected: {e}"

    redis_status = "disconnected"
    try:
        import redis

        r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=1.0)
        if r.ping():
            redis_status = "connected"
        r.close()
    except Exception as e:  # noqa: BLE001 # Health probe service diagnostic fallback
        redis_status = f"disconnected: {e}"

    active_jobs = 0
    worker_liveness = "idle"
    try:
        from app.jobs.repository import JobRepository

        repo = JobRepository()
        running_jobs = repo.list_jobs(status="RUNNING")
        active_jobs = len(running_jobs)
        if redis_status == "connected":
            worker_liveness = "active" if active_jobs > 0 else "ready"
        else:
            worker_liveness = "in_memory_fallback"
    except Exception as e:  # noqa: BLE001 # Health probe job repository fallback
        import logging

        logging.getLogger(__name__).debug(f"Health check job repository lookup failed: {e}")

    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "llm_provider": settings.LLM_PROVIDER,
        "embedding_model": settings.EMBEDDING_MODEL,
        "databases": {
            "neo4j": neo4j_status,
            "qdrant": qdrant_status,
        },
        "queue": {
            "redis": redis_status,
            "worker_status": worker_liveness,
            "active_jobs_count": active_jobs,
        },
    }
