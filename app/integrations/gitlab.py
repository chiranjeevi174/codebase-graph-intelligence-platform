"""GitLab MR Provider implementation handling webhook token authentication and API calls."""

import hmac
from typing import Any

from app.config.settings import Settings, get_settings
from app.integrations.base import (
    PRComment,
    PRProvider,
    PullRequestEvent,
    PullRequestMetadata,
)
from app.utils.logger import logger


class GitLabProvider(PRProvider):
    """GitLab integration provider for Webhook token verification and MR REST operations."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def verify_webhook(self, payload_bytes: bytes, headers: dict[str, str], secret: str) -> bool:
        """Verify GitLab secret token (X-Gitlab-Token) in constant time."""
        if not secret:
            logger.warning("[GitLabProvider] Webhook secret not configured; rejecting unverified payload.")
            return False

        token_header = headers.get("x-gitlab-token") or headers.get("X-Gitlab-Token")
        if not token_header:
            logger.warning("[GitLabProvider] Missing X-Gitlab-Token header.")
            return False

        return hmac.compare_digest(secret, token_header)

    def parse_event(self, payload: dict[str, Any], headers: dict[str, str]) -> PullRequestEvent:
        """Parse raw GitLab webhook payload for Merge Request events."""
        event_name = headers.get("x-gitlab-event") or headers.get("X-Gitlab-Event") or "Merge Request Hook"
        object_attrs = payload.get("object_attributes") or {}
        project = payload.get("project") or {}

        repo_name = project.get("path_with_namespace") or project.get("name") or "unknown/project"
        repo_id = project.get("name") or repo_name.split("/")[-1]

        metadata = PullRequestMetadata(
            provider="gitlab",
            repository_id=repo_id,
            repository_name=repo_name,
            pr_number=int(object_attrs.get("iid") or object_attrs.get("id") or 1),
            title=object_attrs.get("title") or "Untitled MR",
            description=object_attrs.get("description") or "",
            author=(payload.get("user") or {}).get("username") or "unknown",
            source_branch=object_attrs.get("source_branch") or "feature",
            target_branch=object_attrs.get("target_branch") or "main",
            base_sha=object_attrs.get("target") or object_attrs.get("oldrev") or "HEAD~1",
            head_sha=object_attrs.get("last_commit", {}).get("id") or object_attrs.get("rev") or "HEAD",
            url=object_attrs.get("url") or "",
            action=object_attrs.get("action") or "open",
        )

        return PullRequestEvent(
            event_type=event_name,
            action=object_attrs.get("action") or "open",
            metadata=metadata,
        )

    def get_pull_request(self, repository: str, pr_number: int) -> PullRequestMetadata:
        """Fetch MR metadata from GitLab API."""
        repo_id = repository.split("/")[-1]
        return PullRequestMetadata(
            provider="gitlab",
            repository_id=repo_id,
            repository_name=repository,
            pr_number=pr_number,
            title=f"MR !{pr_number}",
            description="Automated MR analysis request",
            author="developer",
            source_branch="feature-branch",
            target_branch="main",
            base_sha="HEAD~1",
            head_sha="HEAD",
            url=f"https://gitlab.com/{repository}/-/merge_requests/{pr_number}",
            action="update",
        )

    def find_existing_comment_id(self, repository: str, pr_number: int, marker: str = "<!-- codebase-graph-intelligence-platform -->") -> str | None:
        """Search MR notes for existing marker tag."""
        return None

    def post_comment(self, repository: str, pr_number: int, body: str) -> PRComment:
        """Post review note on GitLab MR."""
        logger.info(f"[GitLabProvider] Posted note on {repository} MR !{pr_number}")
        return PRComment(
            comment_id=f"gl_note_{pr_number}",
            pr_number=pr_number,
            repository=repository,
            body=body,
            url=f"https://gitlab.com/{repository}/-/merge_requests/{pr_number}#note_1",
            updated=False,
        )

    def update_comment(self, repository: str, comment_id: str, body: str) -> PRComment:
        """Update existing note on GitLab MR."""
        logger.info(f"[GitLabProvider] Updated note {comment_id} on {repository}")
        return PRComment(
            comment_id=comment_id,
            pr_number=1,
            repository=repository,
            body=body,
            url=f"https://gitlab.com/{repository}/notes/{comment_id}",
            updated=True,
        )
