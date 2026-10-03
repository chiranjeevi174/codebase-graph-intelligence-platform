from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class PRJobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DEAD_LETTER = "DEAD_LETTER"


class PRCommentStatus(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    POSTED = "POSTED"
    FAILED = "FAILED"
    SKIPPED_DRY_RUN = "SKIPPED_DRY_RUN"


class PRAction(str, Enum):
    OPENED = "OPENED"
    UPDATED = "UPDATED"
    REOPENED = "REOPENED"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class PRJobRequest(BaseModel):
    """Request params for submitting an async or sync PR analysis job."""

    provider: str = Field(default="github", description="PR provider platform e.g. github, gitlab")
    repository: str = Field(..., description="Repository full name e.g. owner/repo")
    pr_number: int = Field(default=1, description="Pull/Merge request number")
    repo_path: str = Field(default=".", description="Path to local repository directory")
    base_ref: str = Field(default="HEAD~1", description="Base Git ref")
    target_ref: str = Field(default="HEAD", description="Target Git ref")
    dry_run: bool = Field(default=True, description="True if running in dry-run mode without posting platform comments")
    max_hops: int = Field(default=3, description="Maximum graph traversal depth")
    wait: bool = Field(default=False, description="If True, block safely and wait for completion. Default False returns 202 Accepted job")
    provider_delivery_id: str | None = Field(default=None, description="Optional webhook delivery event ID")
    action: PRAction = Field(default=PRAction.OPENED, description="Normalized PR/MR action event")


class PRAnalysisJob(BaseModel):
    """Structured container tracking PR analysis job lifecycle and status metadata."""

    job_id: str = Field(..., description="Unique deterministic job identifier e.g. pr_job_123")
    provider: str = Field(..., description="Provider e.g. github, gitlab")
    repository: str = Field(..., description="Repository full name")
    pr_number: int = Field(..., description="PR/MR ID number")
    base_sha: str = Field(default="HEAD~1", description="Base commit SHA")
    head_sha: str = Field(default="HEAD", description="Target/head commit SHA")
    repo_path: str = Field(default=".", description="Local repository path")
    dry_run: bool = Field(default=True, description="Dry run status")
    max_hops: int = Field(default=3, description="Max hops")
    status: PRJobStatus = Field(default=PRJobStatus.QUEUED, description="Current job status")
    comment_status: PRCommentStatus = Field(default=PRCommentStatus.PENDING, description="Platform comment posting status")
    attempt: int = Field(default=1, description="Current execution attempt count")
    max_attempts: int = Field(default=3, description="Maximum retry attempts")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO 8601 creation timestamp")
    queued_at: str | None = Field(default=None, description="ISO 8601 queue timestamp")
    started_at: str | None = Field(default=None, description="ISO 8601 execution start timestamp")
    completed_at: str | None = Field(default=None, description="ISO 8601 completion timestamp")
    error: str | None = Field(default=None, description="Safe error message if job failed")
    analysis_run_id: str | None = Field(default=None, description="Result analysis run ID")
    result_reference: str | None = Field(default=None, description="URI reference to job result")
    worker_id: str | None = Field(default=None, description="Worker runtime identifier")
    duration_ms: float | None = Field(default=None, description="Job execution duration in milliseconds")
    retry_count: int = Field(default=0, description="Total retries performed")
    failure_type: str | None = Field(default=None, description="Classification of failure e.g. transient, permanent")
    provider_delivery_id: str | None = Field(default=None, description="Webhook delivery UUID")
    action: PRAction = Field(default=PRAction.OPENED, description="Normalized PR event action")


class PRAnalysisRun(BaseModel):
    """Historical record of an individual PR analysis run for a specific commit SHA."""

    analysis_run_id: str = Field(..., description="Unique analysis run ID")
    job_id: str = Field(..., description="Associated job ID")
    provider: str = Field(..., description="Provider e.g. github, gitlab")
    repository: str = Field(..., description="Repository full name")
    pr_number: int = Field(..., description="PR/MR number")
    base_sha: str = Field(..., description="Base commit SHA")
    head_sha: str = Field(..., description="Head commit SHA")
    status: PRJobStatus = Field(..., description="Completion status of analysis run")
    created_at: str = Field(..., description="Creation timestamp")
    started_at: str | None = Field(default=None, description="Start timestamp")
    completed_at: str | None = Field(default=None, description="Completion timestamp")
    result_reference: str | None = Field(default=None, description="Result report reference URL")
    comment_status: PRCommentStatus = Field(default=PRCommentStatus.NOT_REQUESTED, description="Comment posting status")


class PRJobResult(BaseModel):
    """Structured result container for async PR job status and report payload."""

    job_id: str = Field(..., description="Unique job identifier")
    status: PRJobStatus = Field(..., description="Current job status")
    comment_status: PRCommentStatus = Field(default=PRCommentStatus.NOT_REQUESTED, description="Platform comment status")
    analysis_run_id: str | None = Field(default=None, description="Result analysis run ID")
    error: str | None = Field(default=None, description="Error message if job failed")
    result: Any | None = Field(default=None, description="PRAnalysisResult dictionary or object")
    worker_id: str | None = Field(default=None, description="Worker runtime identifier")
    duration_ms: float | None = Field(default=None, description="Total execution duration in milliseconds")
    retry_count: int = Field(default=0, description="Retry attempt count")



