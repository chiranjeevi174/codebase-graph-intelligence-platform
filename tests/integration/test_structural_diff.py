"""Integration tests for structural Git diff and change impact analysis."""

import os
import shutil
import subprocess
from pathlib import Path
import pytest

from app.diff.diff_analyzer import StructuralDiffAnalyzer
from app.diff.diff_models import ChangeClassification, ChangeType, DiffRequest


@pytest.fixture
def temp_git_repo(tmp_path):
    """Fixture that initializes a temporary Git repository with two deterministic commits."""
    repo_dir = tmp_path / "diff_repo"
    repo_dir.mkdir()

    fixtures_dir = Path(__file__).parent.parent / "fixtures" / "diff_repo"
    v1_dir = fixtures_dir / "v1"
    v2_dir = fixtures_dir / "v2"

    def run_git(args):
        res = subprocess.run(
            ["git"] + args,
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()

    # 1. Initialize git repo
    run_git(["init"])
    run_git(["config", "user.name", "Test User"])
    run_git(["config", "user.email", "test@example.com"])

    # 2. Copy V1 files and commit
    for f in v1_dir.glob("*"):
        if f.is_file():
            shutil.copy(f, repo_dir / f.name)

    run_git(["add", "."])
    run_git(["commit", "-m", "Commit A"])
    commit_a = run_git(["rev-parse", "HEAD"])

    # 3. Copy V2 files and commit
    for f in v2_dir.glob("*"):
        if f.is_file():
            shutil.copy(f, repo_dir / f.name)

    run_git(["add", "."])
    run_git(["commit", "-m", "Commit B"])
    commit_b = run_git(["rev-parse", "HEAD"])

    return str(repo_dir), commit_a, commit_b


@pytest.mark.integration
def test_structural_git_diff_end_to_end(temp_git_repo):
    repo_path, commit_a, commit_b = temp_git_repo

    analyzer = StructuralDiffAnalyzer()
    req = DiffRequest(
        repository_id="test_diff_repo",
        repo_path=repo_path,
        base_ref=commit_a,
        target_ref=commit_b,
        max_hops=3,
    )

    result = analyzer.analyze_diff(req)

    assert result.base_ref == commit_a
    assert result.target_ref == commit_b
    assert result.structural_diff.base_commit_hash == commit_a
    assert result.structural_diff.target_commit_hash == commit_b

    # 1. File-level diff verification
    files_changed = {f.file_path: f.status for f in result.structural_diff.files_changed}
    assert "user_service.py" in files_changed
    assert "api_routes.py" in files_changed

    # 2. Symbol-level diff verification
    symbols_changed = result.structural_diff.symbols_changed
    assert len(symbols_changed) > 0

    create_user_chg = next((s for s in symbols_changed if s.symbol_name == "create_user"), None)
    assert create_user_chg is not None
    assert create_user_chg.change_type in (ChangeType.MODIFIED, ChangeType.ADDED)
    assert create_user_chg.signature_change is not None
    assert create_user_chg.signature_change.signature_changed is True
    assert "role" in create_user_chg.signature_change.parameter_added

    # 3. API endpoint diff verification
    api_changes = result.structural_diff.api_changes
    assert len(api_changes) > 0
    removed_ep = next((a for a in api_changes if a.endpoint_removed or a.change_type == ChangeType.REMOVED), None)
    added_ep = next((a for a in api_changes if a.endpoint_added or a.change_type == ChangeType.ADDED), None)
    assert removed_ep is not None or added_ep is not None

    # 4. Classification & Affected Files
    assert result.classification in (
        ChangeClassification.POTENTIALLY_BREAKING.value,
        ChangeClassification.STRUCTURAL_CHANGE.value,
    )
    assert len(result.affected_files) > 0
    assert "user_service.py" in result.affected_files

    # 5. LLM Explanation / Summary presence
    assert result.explanation is not None
    assert len(result.explanation) > 0
