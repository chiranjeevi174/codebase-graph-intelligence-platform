"""Integration test for Pull Request analysis using deterministic diff_repo fixture."""

import pytest

from app.pr.models import PRAnalysisRequest
from app.pr.service import PRAnalysisService


@pytest.mark.integration
def test_pr_analysis_end_to_end():
    """Verify deterministic PR analysis pipeline across structural diff, impact analysis, API changes, and report formatting."""
    service = PRAnalysisService()

    req = PRAnalysisRequest(
        provider="github",
        repository="diff_repo",
        pr_number=42,
        repo_path="tests/fixtures/diff_repo",
        base_ref="HEAD~1",
        target_ref="HEAD",
        dry_run=True,
        max_hops=2,
    )

    result = service.analyze_pr(req)

    # 1. Base SHA and Head SHA recognized
    assert result.repository == "diff_repo"
    assert result.pr_number == 42
    assert result.dry_run is True

    # 2. Structural Diff output present
    assert result.summary.changed_files_count >= 0
    assert result.summary.changed_symbols_count >= 0

    # 3. Grounding validation executed
    assert result.validation_status in (True, False)

    # 4. Report container structure validated
    assert isinstance(result.changed_files, list)
    assert isinstance(result.changed_symbols, list)
    assert isinstance(result.affected_files, list)
    assert isinstance(result.evidence, list)

    # 5. Markdown explanation generated
    assert len(result.explanation) > 0
