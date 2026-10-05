"""Unit test suite for PR Analysis, Webhook verification, Idempotency, and Comment Formatting."""

import hmac
import hashlib
from app.config.settings import get_settings
from app.integrations.factory import PRProviderFactory
from app.integrations.github import GitHubProvider
from app.integrations.gitlab import GitLabProvider
from app.pr.comment_formatter import MARKER, PRCommentFormatter
from app.pr.models import PRAnalysisRequest, PRAnalysisResult, PRAnalysisSummary
from app.pr.service import PRAnalysisService
from app.pr.webhook_service import PRWebhookService


def test_provider_factory():
    """Verify PRProviderFactory instantiates GitHub and GitLab providers correctly."""
    gh = PRProviderFactory.get_provider("github")
    gl = PRProviderFactory.get_provider("gitlab")
    assert isinstance(gh, GitHubProvider)
    assert isinstance(gl, GitLabProvider)


def test_github_webhook_verification():
    """Verify GitHub HMAC-SHA256 signature verification in constant time."""
    provider = GitHubProvider()
    secret = "secret_key_123"
    body = b'{"action":"opened","number":1}'

    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {"X-Hub-Signature-256": sig}

    assert provider.verify_webhook(body, headers, secret) is True
    assert provider.verify_webhook(body, {"X-Hub-Signature-256": "sha256=invalid"}, secret) is False
    assert provider.verify_webhook(body, {}, secret) is False


def test_gitlab_webhook_verification():
    """Verify GitLab secret token verification in constant time."""
    provider = GitLabProvider()
    secret = "gitlab_secret_456"
    headers = {"X-Gitlab-Token": secret}

    assert provider.verify_webhook(b"{}", headers, secret) is True
    assert provider.verify_webhook(b"{}", {"X-Gitlab-Token": "wrong"}, secret) is False


def test_github_event_parsing():
    """Verify GitHub webhook payload parsing into structured event models."""
    provider = GitHubProvider()
    payload = {
        "action": "synchronize",
        "number": 42,
        "repository": {"full_name": "owner/repo", "name": "repo"},
        "pull_request": {
            "title": "Fix user service",
            "body": "Fixes bug in user service",
            "user": {"login": "dev1"},
            "head": {"ref": "feature", "sha": "headsha123"},
            "base": {"ref": "main", "sha": "basesha456"},
            "html_url": "https://github.com/owner/repo/pull/42",
        },
    }
    event = provider.parse_event(payload, {"X-GitHub-Event": "pull_request"})
    meta = event.metadata

    assert meta.provider == "github"
    assert meta.repository_name == "owner/repo"
    assert meta.pr_number == 42
    assert meta.author == "dev1"
    assert meta.head_sha == "headsha123"
    assert meta.base_sha == "basesha456"


def test_comment_formatter_and_marker():
    """Verify PRCommentFormatter renders structured Markdown with the stable marker."""
    res = PRAnalysisResult(
        analysis_run_id="run_123",
        provider="github",
        repository="owner/repo",
        pr_number=10,
        base_sha="basesha",
        head_sha="headsha",
        summary=PRAnalysisSummary(
            changed_files_count=2,
            changed_symbols_count=3,
            signature_changes_count=1,
            api_changes_count=1,
            affected_files_count=4,
            cross_language_impacts_count=1,
        ),
        changed_files=["service.py", "client.ts"],
        changed_symbols=[{"symbol_name": "UserService", "file_path": "service.py", "change_type": "MODIFIED"}],
        signature_changes=[{"symbol_name": "UserService.create", "old_signature": "create(a)", "new_signature": "create(a, b)"}],
        api_changes=[{"endpoint_id": "GET:/api/users", "http_method": "GET", "path": "/api/users", "change_type": "MODIFIED"}],
        affected_components=["UserController (controller.py:15)"],
        affected_files=["service.py", "controller.py"],
        cross_language_impacts=[{"description": "ClientCall -> ApiEndpoint"}],
        explanation="Static analysis identifies downstream components.",
        validation_status=True,
        dry_run=True,
    )

    formatted = PRCommentFormatter.format_comment(res)
    assert MARKER in formatted
    assert "## Codebase Intelligence Analysis" in formatted
    assert "Changed Files:** 2" in formatted
    assert "UserService" in formatted
    assert "GET /api/users" in formatted


def test_pr_analysis_service_dry_run():
    """Verify PRAnalysisService executes dry-run without posting comments."""
    service = PRAnalysisService()
    req = PRAnalysisRequest(
        provider="github",
        repository="sample_repo",
        pr_number=1,
        repo_path="tests/fixtures/sample_repo",
        base_ref="HEAD~1",
        target_ref="HEAD",
        dry_run=True,
    )

    result = service.analyze_pr(req)
    assert result.provider == "github"
    assert result.pr_number == 1
    assert result.dry_run is True
    assert result.comment is None
    assert result.analysis_run_id.startswith("pr_run_")


def test_webhook_idempotency_caching():
    """Verify PRWebhookService caches analysis results by idempotency key."""
    settings = get_settings()
    orig_secret = settings.GITHUB_WEBHOOK_SECRET
    settings.GITHUB_WEBHOOK_SECRET = "testsecret"

    try:
        service = PRWebhookService(settings=settings)
        payload = {
            "action": "opened",
            "number": 5,
            "repository": {"full_name": "org/repo", "name": "repo"},
            "pull_request": {
                "title": "PR Test",
                "head": {"ref": "feat", "sha": "sha12345"},
                "base": {"ref": "main", "sha": "sha67890"},
            },
        }
        body = b'{"action":"opened"}'
        sig = "sha256=" + hmac.new(b"testsecret", body, hashlib.sha256).hexdigest()
        headers = {"X-Hub-Signature-256": sig}

        res1 = service.process_webhook("github", body, payload, headers, repo_path="tests/fixtures/sample_repo", dry_run=True)
        res2 = service.process_webhook("github", body, payload, headers, repo_path="tests/fixtures/sample_repo", dry_run=True)

        assert res1.analysis_run_id == res2.analysis_run_id
    finally:
        settings.GITHUB_WEBHOOK_SECRET = orig_secret
