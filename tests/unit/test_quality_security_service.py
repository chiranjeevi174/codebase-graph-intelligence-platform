"""Unit tests for Code Quality & Security Analysis Service."""

from pathlib import Path

from app.analysis.quality_security_service import CodeQualitySecurityService
from app.models.entities import FindingCategory, QualitySecurityAnalysisRequest, SeverityLevel


def test_quality_security_sample_repo_scan():
    """Verify quality and security scanner on sample_repo fixture."""
    service = CodeQualitySecurityService()
    req = QualitySecurityAnalysisRequest(
        repository_id="sample_repo",
        repo_path=str(Path("tests/fixtures/sample_repo").resolve()),
        categories=["quality", "security"],
    )
    result = service.analyze(req)

    assert result.repository_id == "sample_repo"
    assert result.summary.files_scanned > 0
    assert result.explanation is not None
    assert len(result.explanation) > 50


def test_secret_redaction_and_masking(tmp_path):
    """Verify hardcoded API keys and secrets are masked and never exposed in findings."""
    test_file = tmp_path / "secrets_leak.py"
    secret_token = "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890"
    test_file.write_text(f'OPENAI_API_KEY = "{secret_token}"\n', encoding="utf-8")

    service = CodeQualitySecurityService()
    req = QualitySecurityAnalysisRequest(
        repository_id="test_repo",
        repo_path=str(tmp_path),
        categories=["security"],
    )
    result = service.analyze(req)

    # Must detect secret
    secret_findings = [f for f in result.findings if f.rule_id.startswith("SEC-001")]
    assert len(secret_findings) >= 1
    finding = secret_findings[0]

    # Verify severity is Critical or High
    assert finding.severity in (SeverityLevel.CRITICAL, SeverityLevel.HIGH)
    assert finding.category == FindingCategory.SECURITY

    # Crucial Requirement: The raw secret MUST NOT appear in finding evidence or explanation!
    assert secret_token not in finding.code_evidence
    assert secret_token not in finding.explanation
    assert "[REDACTED]" in finding.code_evidence or "********" in finding.code_evidence


def test_sql_and_command_injection_detection(tmp_path):
    """Verify detection of SQL injection string interpolation and unsafe shell command execution."""
    vuln_file = tmp_path / "vuln_service.py"
    vuln_file.write_text(
        """
import os
import subprocess

def search_user(user_id):
    # Potential SQL Injection
    cursor.execute(f"SELECT * FROM users WHERE id = '{user_id}'")

def run_backup(backup_cmd):
    # Potential Command Injection
    os.system(backup_cmd)
    subprocess.Popen(backup_cmd, shell=True)
""",
        encoding="utf-8",
    )

    service = CodeQualitySecurityService()
    req = QualitySecurityAnalysisRequest(
        repository_id="test_vuln_repo",
        repo_path=str(tmp_path),
        categories=["security"],
    )
    result = service.analyze(req)

    rule_ids = {f.rule_id for f in result.findings}
    assert "SEC-003" in rule_ids  # SQL Injection
    assert "SEC-004" in rule_ids  # Command Injection


def test_code_smells_detection(tmp_path):
    """Verify detection of code smells (wildcard imports, silent exception suppression, mutable defaults)."""
    smell_file = tmp_path / "smelly_code.py"
    smell_file.write_text(
        """
from os import *

def dangerous_default(items=[]):
    try:
        items.append(1)
    except Exception:
        pass
""",
        encoding="utf-8",
    )

    service = CodeQualitySecurityService()
    req = QualitySecurityAnalysisRequest(
        repository_id="test_smell_repo",
        repo_path=str(tmp_path),
        categories=["quality"],
    )
    result = service.analyze(req)

    rule_ids = {f.rule_id for f in result.findings}
    assert "QUAL-004" in rule_ids  # Wildcard import
    assert "QUAL-005" in rule_ids  # Mutable default
    assert "QUAL-003" in rule_ids  # Silent exception suppression
