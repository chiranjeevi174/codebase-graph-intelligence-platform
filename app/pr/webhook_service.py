"""PR Webhook Service handling signature verification, event parsing, and idempotency."""

from typing import Any

from app.config.settings import Settings, get_settings
from app.integrations.factory import PRProviderFactory
from app.pr.models import PRAnalysisRequest, PRAnalysisResult
from app.pr.service import PRAnalysisService
from app.utils.logger import logger


class PRWebhookService:
    """Orchestrates incoming webhooks, authenticity verification, idempotency, and analysis execution."""

    # In-memory idempotency cache: run_key -> PRAnalysisResult
    _ANALYSIS_CACHE: dict[str, PRAnalysisResult] = {}

    def __init__(self, pr_service: PRAnalysisService | None = None, settings: Settings | None = None):
        self.pr_service = pr_service or PRAnalysisService()
        self.settings = settings or get_settings()

    def process_webhook(
        self,
        provider_name: str,
        payload_bytes: bytes,
        payload_dict: dict[str, Any],
        headers: dict[str, str],
        repo_path: str = ".",
        dry_run: bool = True,
    ) -> PRAnalysisResult:
        """Verify webhook signature, parse event, enforce idempotency, and run PR analysis."""
        provider = PRProviderFactory.get_provider(provider_name, settings=self.settings)

        # 1. Verification
        secret = self.settings.GITHUB_WEBHOOK_SECRET if provider_name == "github" else self.settings.GITLAB_WEBHOOK_SECRET
        if secret:
            if not provider.verify_webhook(payload_bytes, headers, secret):
                logger.warning(f"[PRWebhookService] Webhook verification failed for provider '{provider_name}'.")
                raise ValueError("Invalid webhook signature or token authorization failed.")
            logger.info(f"[PRWebhookService:pr_webhook_verified] Verified {provider_name} webhook signature.")
        else:
            logger.info(f"[PRWebhookService:pr_webhook_received] Received {provider_name} webhook (secret unconfigured).")

        # 2. Event Parsing
        event = provider.parse_event(payload_dict, headers)
        meta = event.metadata

        # 3. Idempotency Check
        idempotency_key = f"{provider_name}:{meta.repository_name}:{meta.pr_number}:{meta.head_sha}"
        if idempotency_key in self._ANALYSIS_CACHE:
            logger.info(f"[PRWebhookService] Returning cached idempotency result for key '{idempotency_key}'.")
            return self._ANALYSIS_CACHE[idempotency_key]

        # 4. Trigger Analysis Execution
        analysis_req = PRAnalysisRequest(
            provider=provider_name,
            repository=meta.repository_name,
            pr_number=meta.pr_number,
            repo_path=repo_path,
            base_ref=meta.base_sha,
            target_ref=meta.head_sha,
            dry_run=dry_run,
        )

        result = self.pr_service.analyze_pr(analysis_req)

        # Cache result
        self._ANALYSIS_CACHE[idempotency_key] = result
        return result
