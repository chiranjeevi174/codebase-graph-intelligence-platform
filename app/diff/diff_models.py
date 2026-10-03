"""Pydantic data models for structural Git diff and change impact analysis."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ChangeType(str, Enum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"
    RENAMED = "RENAMED"


class ChangeClassification(str, Enum):
    POTENTIALLY_BREAKING = "potentially_breaking"
    STRUCTURAL_CHANGE = "structural_change"
    NON_BREAKING_CHANGE = "non_breaking_change"


class DiffRequest(BaseModel):
    """Request model for structural Git diff analysis."""

    repository_id: str = Field(default="default", description="Repository identifier")
    repo_path: str = Field(default=".", description="Path to local Git repository")
    base_ref: str = Field(..., description="Base Git reference (e.g. HEAD~1, commit SHA, main)")
    target_ref: str = Field(..., description="Target Git reference (e.g. HEAD, feature-branch)")
    max_hops: int = Field(default=3, description="Maximum traversal depth for impact analysis")
    max_nodes: int = Field(default=50, description="Maximum nodes in impact subgraph")
    max_relationships: int = Field(default=100, description="Maximum relationships to retrieve")


class FileChange(BaseModel):
    """Represents a file-level change between two Git references."""

    repository_id: str = Field(default="default", description="Repository identifier")
    file_path: str = Field(..., description="Target or primary relative file path")
    old_path: str | None = Field(default=None, description="Previous file path if renamed or modified")
    new_path: str | None = Field(default=None, description="New file path if added, modified, or renamed")
    status: ChangeType = Field(..., description="File status (ADDED, REMOVED, MODIFIED, RENAMED)")
    language: str = Field(default="unknown", description="Programming language identifier")
    old_commit: str | None = Field(default=None, description="Base commit hash")
    new_commit: str | None = Field(default=None, description="Target commit hash")


class SignatureChangeInfo(BaseModel):
    """Detailed structural parameter & signature change indicators."""

    signature_changed: bool = Field(default=False, description="True if any public/structural signature aspect changed")
    parameter_added: list[str] = Field(default_factory=list, description="Added parameter names")
    parameter_removed: list[str] = Field(default_factory=list, description="Removed parameter names")
    parameter_order_changed: bool = Field(default=False, description="True if parameter ordering changed")
    default_value_changed: bool = Field(default=False, description="True if parameter default values changed")
    type_annotation_changed: bool = Field(default=False, description="True if parameter type annotations changed")
    return_annotation_changed: bool = Field(default=False, description="True if return type annotation changed")
    old_signature: str | None = Field(default=None, description="Formatted base signature string")
    new_signature: str | None = Field(default=None, description="Formatted target signature string")


class SymbolChange(BaseModel):
    """Represents a code symbol level structural change."""

    repository_id: str = Field(default="default", description="Repository identifier")
    file_path: str = Field(..., description="Relative file path")
    language: str = Field(default="unknown", description="Programming language")
    symbol_name: str = Field(..., description="Unqualified symbol name")
    qualified_name: str = Field(..., description="Fully qualified symbol name")
    symbol_type: str = Field(..., description="Symbol type (Function, Class, Method, etc.)")
    change_type: ChangeType = Field(..., description="Type of change")
    start_line: int = Field(default=0, description="Start line in target version")
    end_line: int = Field(default=0, description="End line in target version")
    old_file_path: str | None = Field(default=None, description="Old file path if changed")
    old_start_line: int | None = Field(default=None, description="Start line in base version")
    old_end_line: int | None = Field(default=None, description="End line in base version")
    new_file_path: str | None = Field(default=None, description="New file path if changed")
    new_start_line: int | None = Field(default=None, description="Start line in target version")
    new_end_line: int | None = Field(default=None, description="End line in target version")
    signature_change: SignatureChangeInfo | None = Field(default=None, description="Signature diff details if applicable")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional properties changed")


class RelationshipChange(BaseModel):
    """Represents an added or removed graph relationship between two structural versions."""

    relationship_type: str = Field(..., description="CALLS, IMPORTS, INHERITS, IMPLEMENTS, DEPENDS_ON, etc.")
    change_type: ChangeType = Field(..., description="ADDED or REMOVED")
    source_symbol: str = Field(..., description="Qualified name or ID of source symbol")
    target_symbol: str = Field(..., description="Qualified name or ID of target symbol")
    old_relationship: dict[str, Any] | None = Field(default=None, description="Relationship metadata in base version")
    new_relationship: dict[str, Any] | None = Field(default=None, description="Relationship metadata in target version")


class ApiChange(BaseModel):
    """Represents a change to an API endpoint or OpenAPI schema."""

    endpoint_id: str = Field(..., description="Endpoint identifier or route key")
    http_method: str = Field(..., description="HTTP method e.g. GET, POST")
    path: str = Field(..., description="API path pattern e.g. /api/users/{id}")
    old_path: str | None = Field(default=None, description="Previous path pattern if changed")
    old_http_method: str | None = Field(default=None, description="Previous HTTP method if changed")
    change_type: ChangeType = Field(..., description="ADDED, REMOVED, MODIFIED")
    endpoint_added: bool = Field(default=False, description="True if endpoint was newly added")
    endpoint_removed: bool = Field(default=False, description="True if endpoint was removed")
    method_changed: bool = Field(default=False, description="True if HTTP method changed")
    path_changed: bool = Field(default=False, description="True if URL path changed")
    operation_id_changed: bool = Field(default=False, description="True if OpenAPI operationId changed")
    request_contract_changed: bool = Field(default=False, description="True if request schema/parameters changed")
    response_contract_changed: bool = Field(default=False, description="True if response schema changed")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional change properties")


class ContractChange(BaseModel):
    """Represents a change to an OpenAPI specification file or API contract."""

    contract_id: str = Field(..., description="Contract path or identifier")
    file_path: str = Field(..., description="File path of contract")
    change_type: ChangeType = Field(..., description="ADDED, REMOVED, MODIFIED")
    details: dict[str, Any] = Field(default_factory=dict, description="Contract diff details")


class StructuralDiff(BaseModel):
    """Complete structural diff comparison result between base and target refs."""

    repository_id: str = Field(default="default", description="Repository identifier")
    base_ref: str = Field(..., description="Base Git ref name or SHA")
    target_ref: str = Field(..., description="Target Git ref name or SHA")
    base_commit_hash: str = Field(default="", description="Resolved base commit SHA")
    target_commit_hash: str = Field(default="", description="Resolved target commit SHA")
    files_changed: list[FileChange] = Field(default_factory=list, description="File-level changes")
    symbols_changed: list[SymbolChange] = Field(default_factory=list, description="Symbol-level changes")
    relationships_changed: list[RelationshipChange] = Field(default_factory=list, description="Graph relationship changes")
    api_changes: list[ApiChange] = Field(default_factory=list, description="API endpoint changes")
    contract_changes: list[ContractChange] = Field(default_factory=list, description="Contract file changes")


class ChangeImpact(BaseModel):
    """Impact analysis details for a single changed symbol or endpoint."""

    changed_symbol: str = Field(..., description="Qualified name or ID of changed symbol")
    change_type: ChangeType = Field(..., description="Type of change")
    direct_dependents: list[str] = Field(default_factory=list, description="Symbols directly calling/depending on changed symbol")
    transitive_dependents: list[str] = Field(default_factory=list, description="Symbols transitively depending on changed symbol")
    direct_dependencies: list[str] = Field(default_factory=list, description="Symbols directly called/used by changed symbol")
    transitive_dependencies: list[str] = Field(default_factory=list, description="Symbols transitively used by changed symbol")
    affected_files: list[str] = Field(default_factory=list, description="Source files containing affected components")
    affected_api_endpoints: list[str] = Field(default_factory=list, description="API endpoints affected")
    affected_api_clients: list[str] = Field(default_factory=list, description="Frontend or client call sites affected")
    affected_contracts: list[str] = Field(default_factory=list, description="OpenAPI contracts affected")


class ChangeImpactResult(BaseModel):
    """Top-level structural diff and change impact analysis result."""

    repository_id: str = Field(default="default", description="Repository identifier")
    base_ref: str = Field(..., description="Base Git reference")
    target_ref: str = Field(..., description="Target Git reference")
    structural_diff: StructuralDiff = Field(..., description="Detailed structural diff")
    impact: list[ChangeImpact] = Field(default_factory=list, description="Per-symbol impact analysis")
    affected_files: list[str] = Field(default_factory=list, description="All affected source file paths")
    affected_api_endpoints: list[str] = Field(default_factory=list, description="All affected API endpoint IDs")
    affected_api_clients: list[str] = Field(default_factory=list, description="All affected frontend/client call IDs")
    classification: str = Field(default=ChangeClassification.STRUCTURAL_CHANGE.value, description="Breaking change risk level")
    explanation: str | None = Field(default=None, description="LLM synthesis or structural summary of changes and impact")
    evidence: list[dict[str, Any]] = Field(default_factory=list, description="Supporting evidence items and line references")
