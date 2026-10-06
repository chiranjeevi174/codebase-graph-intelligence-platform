"""Integrations package for GitHub and GitLab platform providers."""

from app.integrations.base import PRComment, PRProvider, PullRequestEvent, PullRequestMetadata
from app.integrations.factory import PRProviderFactory
from app.integrations.github import GitHubProvider
from app.integrations.gitlab import GitLabProvider

__all__ = [
    "GitHubProvider",
    "GitLabProvider",
    "PRComment",
    "PRProvider",
    "PRProviderFactory",
    "PullRequestEvent",
    "PullRequestMetadata",
]
