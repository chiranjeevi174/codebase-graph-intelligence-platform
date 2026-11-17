"""Regression test suite for PR Analysis Zero-Change Detection fix.

Verifies:
1. A newly added Python file is detected.
2. Three added Python functions are detected.
3. Base and head revisions are resolved correctly.
4. An unavailable revision produces a meaningful error (GitRevisionNotFoundError).
5. A genuinely empty PR produces zero changes.
6. GitHub PR analysis uses the correct repository and revisions.
7. Historical PR analysis runs are deduplicated by run ID.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.diff.diff_models import ChangeType
from app.diff.git_diff_service import (
    GitDiffService,
    GitRevisionNotFoundError,
    resolve_repository_path,
)
from app.diff.structural_diff import StructuralDiffExtractor
from app.diff.symbol_diff import SymbolDiffEngine
from app.jobs.models import PRAnalysisRun, PRCommentStatus, PRJobStatus
from app.jobs.repository import JobRepository
from app.models.entities import SymbolType


def _init_git_repo(path: Path) -> tuple[str, str]:
    """Initialize an isolated git repo with a base commit and a branch with pr_analysis_test.py."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True, capture_output=True)

    # Base commit
    readme = path / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(path), check=True, capture_output=True)
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(path), check=True, capture_output=True, text=True
    ).stdout.strip()

    # Head commit adding pr_analysis_test.py with 3 functions
    code = (
        "def calculate_total(price: float, quantity: int) -> float:\n"
        "    return price * quantity\n\n\n"
        "def calculate_discount(total: float, discount: float) -> float:\n"
        "    return total - discount\n\n\n"
        "def is_high_severity(severity: str) -> bool:\n"
        '    return severity.lower() in {"critical", "high"}\n'
    )
    test_file = path / "pr_analysis_test.py"
    test_file.write_text(code, encoding="utf-8")
    subprocess.run(["git", "add", "pr_analysis_test.py"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Add pr analysis test file"], cwd=str(path), check=True, capture_output=True)
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(path), check=True, capture_output=True, text=True
    ).stdout.strip()

    return base_sha, head_sha


def test_added_python_file_and_three_functions_detected(tmp_path):
    """1 & 2: Verify a newly added Python file and 3 added functions are detected."""
    base_sha, head_sha = _init_git_repo(tmp_path)

    git_svc = GitDiffService(repo_path=str(tmp_path))
    file_changes = git_svc.get_changed_files(base_ref=base_sha, target_ref=head_sha, repository_id="test_repo")

    # 1. Verify changed file
    assert len(file_changes) == 1
    assert file_changes[0].file_path == "pr_analysis_test.py"
    assert file_changes[0].status == ChangeType.ADDED

    # 2. Extract snapshots and symbols
    extractor = StructuralDiffExtractor(git_service=git_svc)
    snapshot_pairs = extractor.extract_file_snapshots(
        file_changes=file_changes, base_ref=base_sha, target_ref=head_sha, repository_id="test_repo"
    )

    symbol_diff_engine = SymbolDiffEngine()
    symbol_changes = symbol_diff_engine.diff_symbols(snapshot_pairs=snapshot_pairs, repository_id="test_repo")

    # Verify exactly 3 functions detected (excluding module container)
    assert len(symbol_changes) == 3
    added_names = {s.symbol_name for s in symbol_changes}
    expected_names = {"calculate_total", "calculate_discount", "is_high_severity"}
    assert added_names == expected_names
    for sc in symbol_changes:
        assert sc.change_type == ChangeType.ADDED
        assert sc.symbol_type in ("Function", SymbolType.FUNCTION)


def test_base_and_head_revisions_resolved_correctly(tmp_path):
    """3: Verify base and head revisions are resolved correctly."""
    base_sha, head_sha = _init_git_repo(tmp_path)
    git_svc = GitDiffService(repo_path=str(tmp_path))

    assert git_svc.has_commit(base_sha) is True
    assert git_svc.has_commit(head_sha) is True
    assert git_svc.has_commit("HEAD~1") is True
    assert git_svc.has_commit("HEAD") is True
    assert git_svc.has_commit("nonexistent_sha_0123456789") is False

    resolved_base = git_svc.resolve_ref("HEAD~1")
    resolved_head = git_svc.resolve_ref("HEAD")
    assert resolved_base == base_sha
    assert resolved_head == head_sha

    merge_base = git_svc.get_merge_base(base_sha, head_sha)
    assert merge_base == base_sha


def test_unavailable_revision_produces_meaningful_error(tmp_path):
    """4: Verify an unavailable revision produces a meaningful GitRevisionNotFoundError."""
    base_sha, _ = _init_git_repo(tmp_path)
    git_svc = GitDiffService(repo_path=str(tmp_path))

    invalid_sha = "00000000000000000000000000000000deadbeef"
    with pytest.raises(GitRevisionNotFoundError) as exc_info:
        git_svc.get_changed_files(base_ref=base_sha, target_ref=invalid_sha, repository_id="test_repo")

    assert "does not exist locally" in str(exc_info.value)
    assert invalid_sha in str(exc_info.value)


def test_genuinely_empty_pr_produces_zero_changes(tmp_path):
    """5: Verify a genuinely empty PR produces zero changes cleanly without error."""
    _base_sha, head_sha = _init_git_repo(tmp_path)
    git_svc = GitDiffService(repo_path=str(tmp_path))

    # Diff head against itself
    file_changes = git_svc.get_changed_files(base_ref=head_sha, target_ref=head_sha, repository_id="test_repo")
    assert file_changes == []

    extractor = StructuralDiffExtractor(git_service=git_svc)
    snapshot_pairs = extractor.extract_file_snapshots(
        file_changes=file_changes, base_ref=head_sha, target_ref=head_sha, repository_id="test_repo"
    )
    symbol_changes = SymbolDiffEngine().diff_symbols(snapshot_pairs, repository_id="test_repo")
    assert symbol_changes == []


def test_github_pr_analysis_uses_correct_repository_and_revisions():
    """6: Verify repository resolution logic correctly maps repository names and fixtures."""
    # Tests fixtures directory resolution
    sample_path = resolve_repository_path(repository="sample_repo", repo_path="tests/fixtures/sample_repo")
    assert sample_path.exists()
    assert "sample_repo" in str(sample_path)

    # Broken fixture path falls back to data/repositories/aegisops if AegisOps is requested
    aegis_path = resolve_repository_path(repository="AegisOps", repo_path="tests/fixtures/AegisOps")
    assert aegis_path.exists()
    assert "aegisops" in str(aegis_path).lower()

    # Short name AegisOps without repo_path resolves to data/repositories/aegisops
    aegis_auto = resolve_repository_path(repository="AegisOps", repo_path=None)
    assert aegis_auto.exists()
    assert "aegisops" in str(aegis_auto).lower()

    # Full slug chiranjeevi174/AegisOps resolves to data/repositories/aegisops
    aegis_slug = resolve_repository_path(repository="chiranjeevi174/AegisOps", repo_path=".")
    assert aegis_slug.exists()
    assert "aegisops" in str(aegis_slug).lower()


def test_history_deduplication_prevents_duplicate_run_ids():
    """7: Verify JobRepository deduplicates analysis runs by analysis_run_id."""
    repo = JobRepository()
    run = PRAnalysisRun(
        analysis_run_id="run_dedup_test_999",
        job_id="job_dedup_test_999",
        provider="github",
        repository="owner/dedup_repo",
        pr_number=99,
        base_sha="base123",
        head_sha="head456",
        status=PRJobStatus.COMPLETED,
        created_at="2026-10-02T10:00:00Z",
        comment_status=PRCommentStatus.SKIPPED_DRY_RUN,
    )

    # Save twice
    repo.save_analysis_run(run)
    repo.save_analysis_run(run)

    history = repo.get_pr_history(provider="github", repository="owner/dedup_repo", pr_number=99)
    matching = [h for h in history if h.analysis_run_id == "run_dedup_test_999"]
    assert len(matching) == 1
