"""FastAPI Webhook endpoints for asynchronous GitHub Pull Requests and GitLab Merge Requests."""

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.integrations.factory import PRProviderFactory
from app.jobs.models import PRAction, PRJobRequest
from app.jobs.repository import JobRepository
from app.jobs.service import JobService
from app.utils.logger import logger

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def normalize_action(raw_action: str) -> PRAction:
    """Normalize raw provider event action string to PRAction enum."""
    act = (raw_action or "").lower()
    if act in ("opened", "open"):
        return PRAction.OPENED
    elif act in ("synchronize", "update"):
        return PRAction.UPDATED
    elif act in ("reopened", "reopen"):
        return PRAction.REOPENED
    elif act in ("closed", "close"):
        return PRAction.CLOSED
    return PRAction.UNKNOWN


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(request: Request, response: Response):
    """Receive, authenticate, filter events, deduplicate delivery IDs, enqueue async PR analysis job, and return HTTP 202 Accepted quickly."""
    payload_bytes = await request.body()
    try:
        payload_dict = await request.json()
    except Exception:  # noqa: BLE001 # Webhook JSON payload fallback boundary
        payload_dict = {}

    headers = dict(request.headers)
    provider = PRProviderFactory.get_provider("github")

    # 1. Verification
    secret = provider.settings.GITHUB_WEBHOOK_SECRET
    if secret:
        if not provider.verify_webhook(payload_bytes, headers, secret):
            logger.warning("[GitHubWebhook] Webhook signature verification failed.")
            raise HTTPException(status_code=401, detail="Invalid X-Hub-Signature-256 signature.")
        logger.info("[GitHubWebhook:pr_webhook_verified] Verified GitHub webhook signature.")
    else:
        logger.info("[GitHubWebhook:pr_webhook_received] Received GitHub webhook (unverified, secret unconfigured).")

    # 2. Delivery Deduplication Check
    delivery_id = (
        headers.get("x-github-delivery") or headers.get("X-GitHub-Delivery") or payload_dict.get("delivery_id")
    )
    job_repo = JobRepository()
    if delivery_id and job_repo.is_duplicate_delivery("github", delivery_id):
        logger.info(f"[GitHubWebhook] Duplicate delivery '{delivery_id}' ignored.")
        response.status_code = status.HTTP_202_ACCEPTED
        return {
            "status": "SKIPPED_DUPLICATE_DELIVERY",
            "delivery_id": delivery_id,
            "message": f"Duplicate webhook delivery event '{delivery_id}' ignored.",
        }

    # 3. Event Parsing & Action Normalization
    event = provider.parse_event(payload_dict, headers)
    meta = event.metadata
    action = normalize_action(event.action)

    if delivery_id:
        job_repo.record_delivery("github", delivery_id)

    # 4. Action Filtering Policy
    if action not in (PRAction.OPENED, PRAction.UPDATED, PRAction.REOPENED):
        logger.info(f"[GitHubWebhook] Action '{action.value}' ignored per analysis policy.")
        response.status_code = status.HTTP_202_ACCEPTED
        return {
            "status": "SKIPPED_POLICY",
            "action": action.value,
            "repository": meta.repository_name,
            "pr_number": meta.pr_number,
            "message": f"Event action '{action.value}' ignored per analysis policy.",
        }

    # 5. Create Async Job & Enqueue
    job_req = PRJobRequest(
        provider="github",
        repository=meta.repository_name,
        pr_number=meta.pr_number,
        repo_path="tests/fixtures/sample_repo",
        base_ref=meta.base_sha,
        target_ref=meta.head_sha,
        dry_run=True,
        max_hops=provider.settings.GRAPH_MAX_HOPS,
        wait=False,
        provider_delivery_id=delivery_id,
        action=action,
    )

    job_service = JobService()
    job = await job_service.submit_pr_job(job_req)

    response.status_code = status.HTTP_202_ACCEPTED
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "provider": job.provider,
        "repository": job.repository,
        "pr_number": job.pr_number,
        "action": action.value,
        "created_at": job.created_at,
        "message": "PR analysis job accepted and enqueued.",
    }


@router.post("/gitlab", status_code=status.HTTP_202_ACCEPTED)
async def gitlab_webhook(request: Request, response: Response):
    """Receive, authenticate, filter events, deduplicate delivery IDs, enqueue async MR analysis job, and return HTTP 202 Accepted quickly."""
    payload_bytes = await request.body()
    try:
        payload_dict = await request.json()
    except Exception:  # noqa: BLE001 # Webhook JSON payload fallback boundary
        payload_dict = {}

    headers = dict(request.headers)
    provider = PRProviderFactory.get_provider("gitlab")

    # 1. Verification
    secret = provider.settings.GITLAB_WEBHOOK_SECRET
    if secret:
        if not provider.verify_webhook(payload_bytes, headers, secret):
            logger.warning("[GitLabWebhook] Webhook token verification failed.")
            raise HTTPException(status_code=401, detail="Invalid X-Gitlab-Token authentication failed.")
        logger.info("[GitLabWebhook:pr_webhook_verified] Verified GitLab webhook token.")
    else:
        logger.info("[GitLabWebhook:pr_webhook_received] Received GitLab webhook (unverified, secret unconfigured).")

    # 2. Delivery Deduplication Check
    delivery_id = (
        headers.get("x-gitlab-event-uuid") or headers.get("X-Gitlab-Event-UUID") or payload_dict.get("delivery_id")
    )
    job_repo = JobRepository()
    if delivery_id and job_repo.is_duplicate_delivery("gitlab", delivery_id):
        logger.info(f"[GitLabWebhook] Duplicate delivery '{delivery_id}' ignored.")
        response.status_code = status.HTTP_202_ACCEPTED
        return {
            "status": "SKIPPED_DUPLICATE_DELIVERY",
            "delivery_id": delivery_id,
            "message": f"Duplicate webhook delivery event '{delivery_id}' ignored.",
        }

    # 3. Event Parsing & Action Normalization
    event = provider.parse_event(payload_dict, headers)
    meta = event.metadata
    action = normalize_action(event.action)

    if delivery_id:
        job_repo.record_delivery("gitlab", delivery_id)

    # 4. Action Filtering Policy
    if action not in (PRAction.OPENED, PRAction.UPDATED, PRAction.REOPENED):
        logger.info(f"[GitLabWebhook] Action '{action.value}' ignored per analysis policy.")
        response.status_code = status.HTTP_202_ACCEPTED
        return {
            "status": "SKIPPED_POLICY",
            "action": action.value,
            "repository": meta.repository_name,
            "pr_number": meta.pr_number,
            "message": f"Event action '{action.value}' ignored per analysis policy.",
        }

    # 5. Create Async Job & Enqueue
    job_req = PRJobRequest(
        provider="gitlab",
        repository=meta.repository_name,
        pr_number=meta.pr_number,
        repo_path="tests/fixtures/sample_repo",
        base_ref=meta.base_sha,
        target_ref=meta.head_sha,
        dry_run=True,
        max_hops=provider.settings.GRAPH_MAX_HOPS,
        wait=False,
        provider_delivery_id=delivery_id,
        action=action,
    )

    job_service = JobService()
    job = await job_service.submit_pr_job(job_req)

    response.status_code = status.HTTP_202_ACCEPTED
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "provider": job.provider,
        "repository": job.repository,
        "pr_number": job.pr_number,
        "action": action.value,
        "created_at": job.created_at,
        "message": "MR analysis job accepted and enqueued.",
    }
