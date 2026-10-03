"""Unit tests for GitHubRepositoryLoader URL detection and name extraction."""

from app.ingestion.github_loader import GitHubRepositoryLoader


def test_is_github_url():
    assert GitHubRepositoryLoader.is_github_url("https://github.com/fastapi/fastapi") is True
    assert GitHubRepositoryLoader.is_github_url("https://github.com/fastapi/fastapi.git") is True
    assert GitHubRepositoryLoader.is_github_url("http://github.com/owner/repo/") is True
    assert GitHubRepositoryLoader.is_github_url("D:/local/path/repo") is False
    assert GitHubRepositoryLoader.is_github_url("./relative/path") is False


def test_extract_repo_name():
    assert GitHubRepositoryLoader.extract_repo_name("https://github.com/fastapi/fastapi") == "fastapi"
    assert GitHubRepositoryLoader.extract_repo_name("https://github.com/fastapi/fastapi.git") == "fastapi"
    assert GitHubRepositoryLoader.extract_repo_name("https://github.com/owner/my-repo/") == "my-repo"
