"""Ingestion package exports."""

from app.ingestion.base import RepositoryLoader
from app.ingestion.git_loader import LocalGitLoader
from app.ingestion.github_loader import GitHubRepositoryLoader
from app.ingestion.repository_service import RepositoryIngestionService

__all__ = [
    "GitHubRepositoryLoader",
    "LocalGitLoader",
    "RepositoryIngestionService",
    "RepositoryLoader",
]
