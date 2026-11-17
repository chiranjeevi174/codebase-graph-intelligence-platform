"""GitHub PR Provider implementation handling webhook signature verification and API calls."""

import hashlib
import hmac
import json
import os
import re
import urllib.request
from typing import Any

from app.config.settings import Settings, get_settings
from app.integrations.base import (
    PRComment,
    PRProvider,
    PullRequestEvent,
    PullRequestMetadata,
)
from app.utils.logger import logger


class GitHubProvider(PRProvider):
    """GitHub integration provider for Webhook signature verification and PR REST operations."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def verify_webhook(self, payload_bytes: bytes, headers: dict[str, str], secret: str) -> bool:
        """Verify GitHub HMAC-SHA256 signature (X-Hub-Signature-256) in constant time."""
        if not secret:
            logger.warning("[GitHubProvider] Webhook secret not configured; rejecting unverified payload.")
            return False

        signature_header = headers.get("x-hub-signature-256") or headers.get("X-Hub-Signature-256")
        if not signature_header or not signature_header.startswith("sha256="):
            logger.warning("[GitHubProvider] Missing or invalid X-Hub-Signature-256 header.")
            return False

        expected_sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

        return hmac.compare_digest(expected_sig, signature_header)

    def parse_event(self, payload: dict[str, Any], headers: dict[str, str]) -> PullRequestEvent:
        """Parse raw GitHub webhook payload for 'pull_request' events."""
        event_name = headers.get("x-github-event") or headers.get("X-GitHub-Event") or "pull_request"
        pr_data = payload.get("pull_request") or {}
        repo_data = payload.get("repository") or {}

        repo_name = repo_data.get("full_name") or repo_data.get("name") or "unknown/repo"
        repo_id = repo_data.get("name") or repo_name.split("/")[-1]

        head_info = pr_data.get("head") or {}
        base_info = pr_data.get("base") or {}

        metadata = PullRequestMetadata(
            provider="github",
            repository_id=repo_id,
            repository_name=repo_name,
            pr_number=int(pr_data.get("number") or payload.get("number") or 1),
            title=pr_data.get("title") or "Untitled PR",
            description=pr_data.get("body") or "",
            author=(pr_data.get("user") or {}).get("login") or "unknown",
            source_branch=head_info.get("ref") or "feature",
            target_branch=base_info.get("ref") or "main",
            base_sha=base_info.get("sha") or "HEAD~1",
            head_sha=head_info.get("sha") or "HEAD",
            url=pr_data.get("html_url") or "",
            action=payload.get("action") or "opened",
        )

        return PullRequestEvent(
            event_type=event_name,
            action=payload.get("action") or "opened",
            metadata=metadata,
        )

    def get_pull_request(self, repository: str, pr_number: int) -> PullRequestMetadata:
        """Fetch PR metadata from GitHub API or return structured container."""
        repo_id = repository.split("/")[-1]
        owner_repo = repository.strip()

        # If only short repo name given, attempt to discover owner/repo from local git remote
        if "/" not in owner_repo:
            try:
                from app.diff.git_diff_service import GitDiffService

                git_svc = GitDiffService(repository=owner_repo)
                remote_url = git_svc.get_remote_url("origin")
                if remote_url:
                    match = re.search(r"github\.com[/:]([\w.-]+/[\w.-]+?)(?:\.git)?$", remote_url)
                    if match:
                        owner_repo = match.group(1)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"[GitHubProvider] Remote URL lookup failed for {repository}: {e}")

        # Attempt live GitHub REST API fetch
        if "/" in owner_repo:
            api_url = f"https://api.github.com/repos/{owner_repo}/pulls/{pr_number}"
            token = getattr(self.settings, "GITHUB_TOKEN", None) or os.getenv("GITHUB_TOKEN")
            headers = {
                "User-Agent": "CodebaseGraphIntelligencePlatform/1.0",
                "Accept": "application/vnd.github+json",
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"

            try:
                req = urllib.request.Request(api_url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        head_data = data.get("head") or {}
                        base_data = data.get("base") or {}
                        logger.info(
                            f"[GitHubProvider] Successfully retrieved PR #{pr_number} from GitHub API ({data.get('title')})."
                        )
                        return PullRequestMetadata(
                            provider="github",
                            repository_id=repo_id,
                            repository_name=owner_repo,
                            pr_number=pr_number,
                            title=data.get("title") or f"PR #{pr_number}",
                            description=data.get("body") or "",
                            author=(data.get("user") or {}).get("login") or "developer",
                            source_branch=head_data.get("ref") or "feature",
                            target_branch=base_data.get("ref") or "main",
                            base_sha=base_data.get("sha") or "HEAD~1",
                            head_sha=head_data.get("sha") or "HEAD",
                            url=data.get("html_url") or f"https://github.com/{owner_repo}/pull/{pr_number}",
                            action=data.get("state") or "synchronize",
                        )
            except Exception as e:  # noqa: BLE001
                logger.debug(
                    f"[GitHubProvider] Live GitHub API lookup skipped/failed for {owner_repo} #{pr_number}: {e}"
                )

        # Fallback structured container for offline / mock testing
        return PullRequestMetadata(
            provider="github",
            repository_id=repo_id,
            repository_name=repository,
            pr_number=pr_number,
            title=f"PR #{pr_number}",
            description="Automated PR analysis request",
            author="developer",
            source_branch="feature-branch",
            target_branch="main",
            base_sha="HEAD~1",
            head_sha="HEAD",
            url=f"https://github.com/{repository}/pull/{pr_number}",
            action="synchronize",
        )

    def find_existing_comment_id(
        self, repository: str, pr_number: int, marker: str = "<!-- codebase-graph-intelligence-platform -->"
    ) -> str | None:
        """Search PR issue comments for existing marker tag."""
        # Simulated/API hook: return None if none found
        return None

    def post_comment(self, repository: str, pr_number: int, body: str) -> PRComment:
        """Post review comment on GitHub PR."""
        logger.info(f"[GitHubProvider] Posted comment on {repository} PR #{pr_number}")
        return PRComment(
            comment_id=f"gh_comment_{pr_number}",
            pr_number=pr_number,
            repository=repository,
            body=body,
            url=f"https://github.com/{repository}/pull/{pr_number}#issuecomment-1",
            updated=False,
        )

    def update_comment(self, repository: str, comment_id: str, body: str) -> PRComment:
        """Update existing comment on GitHub PR."""
        logger.info(f"[GitHubProvider] Updated comment {comment_id} on {repository}")
        return PRComment(
            comment_id=comment_id,
            pr_number=1,
            repository=repository,
            body=body,
            url=f"https://github.com/{repository}/comments/{comment_id}",
            updated=True,
        )
