"""Pydantic data models for Pull Request analysis and automated reviews."""

from typing import Any

from pydantic import BaseModel, Field

from app.integrations.base import PRComment


class PRAnalysisRequest(BaseModel):
    """Request model for PR analysis endpoint and manual analysis triggers."""

    provider: str = Field(default="github", description="PR Provider e.g. github, gitlab")
    repository: str = Field(..., description="Repository name or slug e.g. owner/repo")
    pr_number: int = Field(default=1, description="Pull Request or Merge Request number")
    repo_path: str = Field(default=".", description="Path to local repository directory")
    base_ref: str = Field(default="HEAD~1", description="Base Git ref")
    target_ref: str = Field(default="HEAD", description="Target Git ref")
    dry_run: bool = Field(default=True, description="If True, generate report without posting platform comment")
    max_hops: int = Field(default=3, description="Maximum graph traversal depth")
    max_nodes: int = Field(default=50, description="Maximum impact nodes to evaluate")
    max_relationships: int = Field(default=100, description="Maximum relationships to evaluate")


class PRAnalysisSummary(BaseModel):
    """Aggregated structural impact counts for a PR analysis run."""

    changed_files_count: int = 0
    changed_symbols_count: int = 0
    signature_changes_count: int = 0
    api_changes_count: int = 0
    affected_files_count: int = 0
    cross_language_impacts_count: int = 0


class PRAnalysisEvidence(BaseModel):
    """Structured evidence item supporting PR analysis conclusions."""

    symbol: str
    file_path: str
    line_range: str = "1"
    evidence_type: str = "static_graph"  # "static_graph", "vector_chunk", "ast_signature"
    description: str = ""


class PRAnalysisResult(BaseModel):
    """Complete machine-readable PR analysis report and output metadata."""

    analysis_run_id: str = Field(..., description="Unique deterministic execution run ID")
    provider: str = Field(..., description="PR provider e.g. github, gitlab")
    repository: str = Field(..., description="Repository full name")
    pr_number: int = Field(..., description="PR/MR ID number")
    base_sha: str = Field(..., description="Base Git commit hash")
    head_sha: str = Field(..., description="Target/Head Git commit hash")
    summary: PRAnalysisSummary = Field(..., description="Aggregated impact counts")
    changed_files: list[str] = Field(default_factory=list)
    changed_symbols: list[dict[str, Any]] = Field(default_factory=list)
    signature_changes: list[dict[str, Any]] = Field(default_factory=list)
    relationship_changes: list[dict[str, Any]] = Field(default_factory=list)
    api_changes: list[dict[str, Any]] = Field(default_factory=list)
    contract_changes: list[dict[str, Any]] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    cross_language_impacts: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[PRAnalysisEvidence] = Field(default_factory=list)
    explanation: str = Field(default="", description="Grounded LLM explanation")
    validation_status: bool = Field(default=True, description="Grounding validation status")
    comment: PRComment | None = Field(default=None, description="Platform comment details")
    dry_run: bool = Field(default=True, description="True if run in dry-run mode without posting")
