"""Abstract base provider interface for GitHub and GitLab PR/MR platform integrations."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class RepositoryReference(BaseModel):
    """Pydantic model representing git repository reference metadata."""

    repository_id: str
    name: str
    full_name: str
    clone_url: str | None = None
    default_branch: str = "main"


class PullRequestMetadata(BaseModel):
    """Metadata extracted for a Pull Request (GitHub) or Merge Request (GitLab)."""

    provider: str  # "github" or "gitlab"
    repository_id: str
    repository_name: str
    pr_number: int
    title: str
    description: str = ""
    author: str = ""
    source_branch: str
    target_branch: str
    base_sha: str
    head_sha: str
    url: str = ""
    action: str = "opened"  # "opened", "synchronize", "reopened", "closed"


class PullRequestEvent(BaseModel):
    """Pydantic model representing an incoming webhook payload event."""

    event_type: str  # e.g. "pull_request", "merge_request"
    action: str
    metadata: PullRequestMetadata


class PRComment(BaseModel):
    """Representation of a posted or updated PR/MR review comment."""

    comment_id: str
    pr_number: int
    repository: str
    body: str
    url: str | None = None
    updated: bool = False


from app.config.settings import Settings, get_settings


class PRProvider(ABC):
    """Abstract provider interface for PR/MR integrations."""

    def __init__(self, settings: Settings | None = None):
        self.settings: Settings = settings or get_settings()

    @abstractmethod
    def verify_webhook(self, payload_bytes: bytes, headers: dict[str, str], secret: str) -> bool:
        """Verify webhook payload authenticity using constant-time signature comparison."""
        pass

    @abstractmethod
    def parse_event(self, payload: dict[str, Any], headers: dict[str, str]) -> PullRequestEvent:
        """Parse raw webhook JSON payload into structured PullRequestEvent."""
        pass

    @abstractmethod
    def get_pull_request(self, repository: str, pr_number: int) -> PullRequestMetadata:
        """Fetch PR/MR metadata via provider REST API."""
        pass

    @abstractmethod
    def find_existing_comment_id(self, repository: str, pr_number: int, marker: str = "<!-- codebase-graph-intelligence-platform -->") -> str | None:
        """Find ID of existing automated analysis comment matching marker tag."""
        pass

    @abstractmethod
    def post_comment(self, repository: str, pr_number: int, body: str) -> PRComment:
        """Post a new analysis comment on the specified PR/MR."""
        pass

    @abstractmethod
    def update_comment(self, repository: str, comment_id: str, body: str) -> PRComment:
        """Update an existing analysis comment on the specified PR/MR."""
        pass
