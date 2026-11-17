"""Code Quality & Security Analysis Engine.

Performs static AST inspection, security vulnerability checks, secret scanning with redaction,
code smell detection, and architectural quality evaluations across supported languages.
"""

import ast
import re
from collections import defaultdict
from pathlib import Path

from app.llm.factory import get_llm
from app.models.entities import (
    AnalysisFinding,
    FindingCategory,
    QualitySecurityAnalysisRequest,
    QualitySecurityAnalysisResult,
    QualitySecuritySummary,
    SeverityLevel,
)
from app.utils.logger import logger

# Redaction patterns for secrets
SECRET_PATTERNS = [
    (
        r"(?:sk-[a-zA-Z0-9]{20,}|sk-proj-[a-zA-Z0-9_-]{20,})",
        "OpenAI API Key",
        SeverityLevel.CRITICAL,
        "SEC-001A",
    ),
    (
        r"(?:AKIA[0-9A-Z]{16})",
        "AWS Access Key ID",
        SeverityLevel.CRITICAL,
        "SEC-001B",
    ),
    (
        r"(?:ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82})",
        "GitHub Personal Access Token",
        SeverityLevel.CRITICAL,
        "SEC-001C",
    ),
    (
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        "Hardcoded Private Key",
        SeverityLevel.CRITICAL,
        "SEC-001D",
    ),
    (
        r"""(?i)(?:password|passwd|secret_key|api_secret)\s*[:=]\s*['\"][A-Za-z0-9@#$%^&*()_+=-]{8,}['\"]""",
        "Hardcoded Password or Secret Credential",
        SeverityLevel.HIGH,
        "SEC-001E",
    ),
]


class CodeQualitySecurityService:
    """Orchestrates comprehensive static code quality and security vulnerability analysis."""

    def __init__(self):
        pass

    def analyze(self, request: QualitySecurityAnalysisRequest) -> QualitySecurityAnalysisResult:
        """Run complete static analysis on target repository."""
        repo_id = request.repository_id or "sample_repo"
        repo_path = self._resolve_repo_path(repo_id, request.repo_path)
        categories = set(request.categories or ["quality", "security"])

        logger.info(
            f"[QualitySecurityService] Running analysis on '{repo_id}' at '{repo_path}' (Categories: {categories})"
        )

        findings: list[AnalysisFinding] = []
        scanned_files = 0

        supported_exts = {".py", ".ts", ".js", ".go", ".java"}
        for p in repo_path.rglob("*"):
            if (
                p.is_file()
                and p.suffix in supported_exts
                and "node_modules" not in p.parts
                and ".git" not in p.parts
                and "__pycache__" not in p.parts
            ):
                scanned_files += 1
                try:
                    rel_path = str(p.relative_to(repo_path)).replace("\\", "/")
                except ValueError:
                    rel_path = p.name

                file_findings = self._analyze_file(p, rel_path, categories)
                findings.extend(file_findings)

        # Apply min_severity filter if specified
        if request.min_severity:
            findings = self._filter_by_severity(findings, request.min_severity)

        # Aggregate summary
        summary = self._compute_summary(findings, scanned_files)

        # Generate grounded explanation and remediation advice
        explanation = self._generate_explanation(repo_id, summary, findings)

        return QualitySecurityAnalysisResult(
            repository_id=repo_id,
            summary=summary,
            findings=findings,
            explanation=explanation,
        )

    def _resolve_repo_path(self, repo_id: str, requested_path: str | None) -> Path:
        """Resolve valid filesystem path to target repository."""
        if requested_path and Path(requested_path).exists():
            return Path(requested_path)

        candidates = [
            Path("tests/fixtures") / repo_id,
            Path("fixtures") / repo_id,
            Path(repo_id),
            Path("tests/fixtures/sample_repo"),
        ]
        for c in candidates:
            if c.exists() and c.is_dir():
                return c
        return Path("tests/fixtures/sample_repo")

    def _analyze_file(self, file_path: Path, rel_path: str, categories: set[str]) -> list[AnalysisFinding]:
        """Analyze a single file for quality smells and security vulnerabilities."""
        findings: list[AnalysisFinding] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[QualitySecurityService] Failed reading {file_path}: {e}")
            return findings

        lines = content.split("\n")

        # 1. Secret Scanning (Security)
        if "security" in categories:
            findings.extend(self._scan_secrets(rel_path, lines))

        # 2. Pattern-based Security & Quality Checks (all languages)
        findings.extend(self._scan_regex_rules(rel_path, lines, categories))

        # 3. Python AST-based Checks
        if file_path.suffix == ".py":
            findings.extend(self._scan_python_ast(rel_path, content, categories))

        return findings

    def _scan_secrets(self, rel_path: str, lines: list[str]) -> list[AnalysisFinding]:
        """Scan file lines for hardcoded credentials, API keys, and tokens with masking."""
        findings: list[AnalysisFinding] = []
        for line_idx, line in enumerate(lines, start=1):
            # Ignore test assertion lines comparing fixtures
            stripped = line.strip()
            if "assert " in stripped or "test_" in rel_path.lower():
                continue

            for pattern, title, severity, rule_id in SECRET_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    raw_secret = match.group(0)
                    masked_evidence = self._mask_secret(line, raw_secret)
                    findings.append(
                        AnalysisFinding(
                            id=f"{rule_id}_{rel_path}_{line_idx}",
                            title=f"Potential Hardcoded Secret: {title}",
                            category=FindingCategory.SECURITY,
                            severity=severity,
                            file_path=rel_path,
                            line_number=line_idx,
                            end_line=line_idx,
                            code_evidence=masked_evidence,
                            explanation=(
                                f"A hardcoded pattern matching a sensitive credential or secret ({title}) was detected. "
                                "Hardcoded credentials in source control present high risk of unauthorized credential exposure."
                            ),
                            why_it_matters=(
                                "Exposing static API keys or credentials in codebases risks complete compromise of associated "
                                "cloud infrastructure, APIs, and confidential repository data."
                            ),
                            suggested_remediation=(
                                "Extract credentials into environment variables or a secret vault (e.g. AWS Secrets Manager, "
                                "HashiCorp Vault) and load them via configuration at runtime."
                            ),
                            rule_id=rule_id,
                            confidence="High",
                        )
                    )
        return findings

    def _mask_secret(self, line: str, secret: str) -> str:
        """Safely mask confidential token strings in evidence output."""
        if len(secret) <= 8:
            masked = "********"
        else:
            masked = secret[:4] + "****[REDACTED]****" + secret[-3:]
        return line.replace(secret, masked).strip()

    def _scan_regex_rules(self, rel_path: str, lines: list[str], categories: set[str]) -> list[AnalysisFinding]:
        """Pattern-based static rules for SQL injection, command execution, and code smells."""
        findings: list[AnalysisFinding] = []

        for line_idx, line in enumerate(lines, start=1):
            sline = line.strip()
            if sline.startswith(("#", "//", "/*", "*")):
                continue

            # Security: SQL Injection via string formatting / concatenation
            if "security" in categories:
                if re.search(
                    r"""(?i)(?:execute|cursor\.execute|raw_query|query)\s*\(\s*f['\"].*SELECT|INSERT|UPDATE|DELETE""",
                    line,
                ):
                    findings.append(
                        AnalysisFinding(
                            id=f"SEC-003_{rel_path}_{line_idx}",
                            title="Potential SQL Injection via F-String Query Interpolation",
                            category=FindingCategory.SECURITY,
                            severity=SeverityLevel.CRITICAL,
                            file_path=rel_path,
                            line_number=line_idx,
                            end_line=line_idx,
                            code_evidence=sline,
                            explanation="Raw database query is constructed using string interpolation rather than parameterized queries.",
                            why_it_matters="Allows malicious SQL payload injection, enabling data extraction, tampering, or authentication bypass.",
                            suggested_remediation="Refactor to parameterized SQL queries with bind variables (e.g. `cursor.execute('SELECT ... WHERE id = %s', (val,))`).",
                            rule_id="SEC-003",
                            confidence="High",
                        )
                    )

                # Security: Command Injection via shell=True or system()
                if re.search(r"""(?i)(?:subprocess\.(?:Popen|call|run)\(.*shell\s*=\s*True|os\.system\s*\()""", line):
                    findings.append(
                        AnalysisFinding(
                            id=f"SEC-004_{rel_path}_{line_idx}",
                            title="Unsafe Shell Command Execution",
                            category=FindingCategory.SECURITY,
                            severity=SeverityLevel.HIGH,
                            file_path=rel_path,
                            line_number=line_idx,
                            end_line=line_idx,
                            code_evidence=sline,
                            explanation="Spawning system processes via a shell or `os.system` without strict parameter array separation.",
                            why_it_matters="Command injection allows arbitrary OS-level execution if untrusted input reaches the shell string.",
                            suggested_remediation="Use `subprocess.run([...], shell=False)` with argument lists instead of raw shell strings.",
                            rule_id="SEC-004",
                            confidence="High",
                        )
                    )

                # Security: Disabled SSL verification
                if "verify=False" in line or "NODE_TLS_REJECT_UNAUTHORIZED" in line:
                    findings.append(
                        AnalysisFinding(
                            id=f"SEC-006_{rel_path}_{line_idx}",
                            title="Insecure Transport: Disabled TLS/SSL Certificate Verification",
                            category=FindingCategory.SECURITY,
                            severity=SeverityLevel.MEDIUM,
                            file_path=rel_path,
                            line_number=line_idx,
                            end_line=line_idx,
                            code_evidence=sline,
                            explanation="HTTP client request disables TLS certificate validation (`verify=False`).",
                            why_it_matters="Permits Man-in-the-Middle (MitM) attacks where an adversary can intercept or modify network traffic.",
                            suggested_remediation="Enable TLS verification with valid trusted certificate bundles.",
                            rule_id="SEC-006",
                            confidence="High",
                        )
                    )

                # Security: Dynamic code execution
                if re.search(r"""\b(?:eval|exec)\s*\(""", line) and not rel_path.startswith("tests/"):
                    findings.append(
                        AnalysisFinding(
                            id=f"SEC-002_{rel_path}_{line_idx}",
                            title="Dynamic Code Evaluation via eval/exec",
                            category=FindingCategory.SECURITY,
                            severity=SeverityLevel.HIGH,
                            file_path=rel_path,
                            line_number=line_idx,
                            end_line=line_idx,
                            code_evidence=sline,
                            explanation="Invocation of dynamic evaluation interpreter constructs (`eval`/`exec`).",
                            why_it_matters="Dynamic evaluation is dangerous when inputs contain untrusted data, leading to remote code execution.",
                            suggested_remediation="Use explicit parsing, lookup dictionaries, or safe serializers like `json.loads`.",
                            rule_id="SEC-002",
                            confidence="High",
                        )
                    )

            # Quality: Wildcard imports
            if "quality" in categories and re.search(r"""^from\s+[\w.]+\s+import\s+\*""", sline):
                findings.append(
                    AnalysisFinding(
                        id=f"QUAL-004_{rel_path}_{line_idx}",
                        title="Namespace Pollution via Wildcard Import",
                        category=FindingCategory.QUALITY,
                        severity=SeverityLevel.LOW,
                        file_path=rel_path,
                        line_number=line_idx,
                        end_line=line_idx,
                        code_evidence=sline,
                        explanation="Wildcard import (`from x import *`) obscures symbol provenance and risks shadowing variables.",
                        why_it_matters="Reduces readability, impairs static type checkers, and causes silent namespace collisions.",
                        suggested_remediation="Explicitly import required symbols by name (e.g. `from module import SpecificClass`).",
                        rule_id="QUAL-004",
                        confidence="High",
                    )
                )

        return findings

    def _scan_python_ast(self, rel_path: str, content: str, categories: set[str]) -> list[AnalysisFinding]:
        """Deep AST analysis for Python files (complexity, exception handling, smells)."""
        findings: list[AnalysisFinding] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            # Quality: Function Complexity and Line Count
            if "quality" in categories and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_name = node.name
                line_count = (node.end_lineno or node.lineno) - node.lineno + 1
                param_count = len(node.args.args)

                # Parameter Count Smell
                if param_count > 6:
                    findings.append(
                        AnalysisFinding(
                            id=f"QUAL-002_{rel_path}_{node.lineno}",
                            title=f"Excessive Function Parameters in `{fn_name}` ({param_count} params)",
                            category=FindingCategory.QUALITY,
                            severity=SeverityLevel.LOW,
                            file_path=rel_path,
                            line_number=node.lineno,
                            end_line=node.end_lineno,
                            code_evidence=f"def {fn_name}(...): ({param_count} parameters)",
                            explanation=f"Function `{fn_name}` declares {param_count} parameters, exceeding the recommended threshold (6).",
                            why_it_matters="High parameter counts indicate poor encapsulation, high coupling, and caller error propensity.",
                            suggested_remediation="Refactor parameters into a structured Pydantic model, dataclass, or configuration object.",
                            rule_id="QUAL-002",
                            confidence="High",
                        )
                    )

                # Excessive Length Smell
                if line_count > 60:
                    findings.append(
                        AnalysisFinding(
                            id=f"QUAL-001_{rel_path}_{node.lineno}",
                            title=f"Excessive Function Length in `{fn_name}` ({line_count} lines)",
                            category=FindingCategory.QUALITY,
                            severity=SeverityLevel.MEDIUM,
                            file_path=rel_path,
                            line_number=node.lineno,
                            end_line=node.end_lineno,
                            code_evidence=f"def {fn_name}(...): [lines {node.lineno}-{node.end_lineno}]",
                            explanation=f"Function `{fn_name}` spans {line_count} lines of code, exceeding single-responsibility guidelines.",
                            why_it_matters="Long functions are difficult to unit-test, maintain, and reason about concurrently.",
                            suggested_remediation="Decompose the function into modular helper methods with dedicated responsibilities.",
                            rule_id="QUAL-001",
                            confidence="High",
                        )
                    )

                # Mutable default argument smell
                for default_node in node.args.defaults:
                    if isinstance(default_node, (ast.List, ast.Dict, ast.Set)):
                        findings.append(
                            AnalysisFinding(
                                id=f"QUAL-005_{rel_path}_{node.lineno}",
                                title=f"Mutable Default Argument in `{fn_name}`",
                                category=FindingCategory.QUALITY,
                                severity=SeverityLevel.MEDIUM,
                                file_path=rel_path,
                                line_number=node.lineno,
                                end_line=node.lineno,
                                code_evidence=f"def {fn_name}(..., default={type(default_node).__name__})",
                                explanation="Using mutable collections (lists, dicts, sets) as default function argument values.",
                                why_it_matters="Default mutable objects are created once at definition time and shared across all invocations.",
                                suggested_remediation="Use `None` as the default value and initialize the collection inside the function body.",
                                rule_id="QUAL-005",
                                confidence="High",
                            )
                        )

            # Quality: Bare or Silent Exception Handling
            if (
                "quality" in categories
                and isinstance(node, ast.ExceptHandler)
                and len(node.body) == 1
                and isinstance(node.body[0], ast.Pass)
            ):
                exc_name = ast.unparse(node.type) if node.type else "Bare"
                findings.append(
                    AnalysisFinding(
                        id=f"QUAL-003_{rel_path}_{node.lineno}",
                        title=f"Silent Exception Suppression (`except {exc_name}: pass`)",
                        category=FindingCategory.QUALITY,
                        severity=SeverityLevel.MEDIUM,
                        file_path=rel_path,
                        line_number=node.lineno,
                        end_line=node.end_lineno,
                        code_evidence=f"except {exc_name}: pass",
                        explanation="Exception handler suppresses exceptions silently with `pass` without logging or re-raising.",
                        why_it_matters="Hides runtime errors, makes debugging catastrophic failures difficult, and masks regressions.",
                        suggested_remediation="Log the exception with stack trace (`logger.warning(...)`) or handle the condition explicitly.",
                        rule_id="QUAL-003",
                        confidence="High",
                    )
                )

            # Quality: God Class smell
            if "quality" in categories and isinstance(node, ast.ClassDef):
                cls_name = node.name
                method_count = len([m for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))])
                line_count = (node.end_lineno or node.lineno) - node.lineno + 1
                if method_count > 12 or line_count > 300:
                    findings.append(
                        AnalysisFinding(
                            id=f"QUAL-006_{rel_path}_{node.lineno}",
                            title=f"High Structural Coupling / God Class `{cls_name}` ({method_count} methods)",
                            category=FindingCategory.QUALITY,
                            severity=SeverityLevel.MEDIUM,
                            file_path=rel_path,
                            line_number=node.lineno,
                            end_line=node.end_lineno,
                            code_evidence=f"class {cls_name}: ({method_count} methods, {line_count} lines)",
                            explanation=f"Class `{cls_name}` defines {method_count} methods spanning {line_count} lines.",
                            why_it_matters="Classes with too many responsibilities violate the Single Responsibility Principle and increase regression risk.",
                            suggested_remediation="Extract cohesive groups of methods into distinct collaborator services or components.",
                            rule_id="QUAL-006",
                            confidence="Medium",
                        )
                    )

        return findings

    def _filter_by_severity(self, findings: list[AnalysisFinding], min_severity: str) -> list[AnalysisFinding]:
        """Filter findings according to severity threshold."""
        levels = {
            "critical": [SeverityLevel.CRITICAL],
            "high": [SeverityLevel.CRITICAL, SeverityLevel.HIGH],
            "medium": [SeverityLevel.CRITICAL, SeverityLevel.HIGH, SeverityLevel.MEDIUM],
            "low": [SeverityLevel.CRITICAL, SeverityLevel.HIGH, SeverityLevel.MEDIUM, SeverityLevel.LOW],
            "informational": list(SeverityLevel),
        }
        allowed = levels.get(min_severity.lower(), list(SeverityLevel))
        return [f for f in findings if f.severity in allowed]

    def _compute_summary(self, findings: list[AnalysisFinding], scanned_files: int) -> QualitySecuritySummary:
        """Compute aggregated findings counts across categories and severity levels."""
        severity_counts: dict[SeverityLevel, int] = defaultdict(int)
        category_counts: dict[FindingCategory, int] = defaultdict(int)

        for f in findings:
            severity_counts[f.severity] += 1
            category_counts[f.category] += 1

        return QualitySecuritySummary(
            total_findings=len(findings),
            quality_count=category_counts[FindingCategory.QUALITY],
            security_count=category_counts[FindingCategory.SECURITY],
            critical_count=severity_counts[SeverityLevel.CRITICAL],
            high_count=severity_counts[SeverityLevel.HIGH],
            medium_count=severity_counts[SeverityLevel.MEDIUM],
            low_count=severity_counts[SeverityLevel.LOW],
            info_count=severity_counts[SeverityLevel.INFORMATIONAL],
            files_scanned=scanned_files,
        )

    def _generate_explanation(
        self, repo_id: str, summary: QualitySecuritySummary, findings: list[AnalysisFinding]
    ) -> str:
        """Generate structured repository-level summary and remediation guidance using LLM with deterministic fallback."""
        top_issues = findings[:5]
        issues_summary = (
            "\n".join(
                [
                    f"- [{f.severity.value}] {f.title} in `{f.file_path}:{f.line_number or 1}`: {f.explanation}"
                    for f in top_issues
                ]
            )
            or "No critical issues observed."
        )

        prompt = f"""You are a Principal Security Architect and Code Quality Engineer reviewing static analysis findings for repository '{repo_id}'.

Scan Summary:
- Total Files Scanned: {summary.files_scanned}
- Total Findings: {summary.total_findings}
  - Security Vulnerabilities: {summary.security_count} (Critical: {summary.critical_count}, High: {summary.high_count})
  - Code Quality Concerns: {summary.quality_count} (Medium: {summary.medium_count}, Low: {summary.low_count})

Sample Priority Findings:
{issues_summary}

Provide a concise, professional engineering summary:
1. Executive Health Assessment: Overall security posture and codebase maintainability.
2. Immediate Priority Remediations: Clear, actionable steps for the most severe findings.
3. Preventative Engineering Guidance: Practices to prevent future occurrences (secret scanning in CI, lint rules, etc.).

Ground the explanation in the specific findings above. Be clear, technical, and actionable."""

        system_prompt = (
            "You are a Principal Security Engineer and Quality Architect providing grounded, actionable guidance. "
            "Never expose sensitive credentials. Explain technical risks and remediations clearly."
        )

        try:
            llm = get_llm()
            explanation = llm.generate(prompt=prompt, system_prompt=system_prompt, temperature=0.2)
            if explanation and len(explanation.strip()) > 50:
                return explanation
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[QualitySecurityService] LLM explanation generation failed: {e}")

        # Deterministic Grounded Fallback
        return (
            f"### Quality & Security Assessment for `{repo_id}`\n\n"
            f"Static analysis evaluated **{summary.files_scanned} source files**, identifying **{summary.total_findings} total findings** "
            f"(**{summary.security_count} security concerns** and **{summary.quality_count} maintainability issues**).\n\n"
            f"#### Severity Distribution\n"
            f"- **Critical**: {summary.critical_count} | **High**: {summary.high_count} | **Medium**: {summary.medium_count} | **Low**: {summary.low_count}\n\n"
            f"#### Recommended Immediate Actions\n"
            + (
                "\n".join(
                    [
                        f"1. **{f.title}** (`{f.file_path}:{f.line_number or 1}`): {f.suggested_remediation}"
                        for f in top_issues
                    ]
                )
                if top_issues
                else "No high-priority vulnerabilities identified."
            )
            + "\n\n#### Preventive Practices\n"
            "- Integrate pre-commit secret scanning hooks to prevent static token commits.\n"
            "- Enforce parameterized SQL queries and avoid dynamic string formatting in database adapters.\n"
            "- Break down long methods and enforce explicit exception handling in CI pipelines."
        )
