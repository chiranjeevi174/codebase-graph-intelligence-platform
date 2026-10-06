"""Pydantic data models for code intelligence entities and relationships."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SymbolType(str, Enum):
    REPOSITORY = "Repository"
    DIRECTORY = "Directory"
    FILE = "File"
    MODULE = "Module"
    CLASS = "Class"
    INTERFACE = "Interface"
    STRUCT = "Struct"
    FUNCTION = "Function"
    METHOD = "Method"
    CONSTRUCTOR = "Constructor"
    TYPE_ALIAS = "TypeAlias"
    PARAMETER = "Parameter"
    VARIABLE = "Variable"
    API = "API"
    DOCUMENTATION = "Documentation"


class RepositoryInfo(BaseModel):
    """Metadata representing an ingested repository."""

    repository_id: str = Field(..., description="Unique identifier or normalized name of repository")
    name: str = Field(..., description="Repository name")
    source: str = Field(default="local", description="Source type: local path or github URL")
    local_path: str = Field(default="", description="Local directory path")
    path: str = Field(..., description="Local directory path or remote URL")
    commit_hash: str | None = Field(default=None, description="Git commit hash if available")
    branch: str = Field(default="main", description="Default or checked-out branch name")
    default_branch: str = Field(default="main", description="Default branch name")
    file_count: int = Field(default=0, description="Total source files enumerated")
    total_files: int = Field(default=0, description="Total source files enumerated")
    languages: list[str] = Field(default_factory=list, description="Detected programming languages")
    language_statistics: dict[str, int] = Field(default_factory=dict, description="File counts by language")


class IngestionResult(BaseModel):
    """Detailed summary of repository ingestion execution."""

    repository_id: str
    name: str
    source: str
    local_path: str
    commit_hash: str | None = None
    status: str = "completed"
    files_discovered: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    symbols_extracted: int = 0
    relationships_extracted: int = 0
    chunks_created: int = 0
    graph_nodes_created: int = 0
    graph_relationships_created: int = 0
    vectors_created: int = 0
    errors: list[str] = Field(default_factory=list)


class SourceFile(BaseModel):
    """Metadata representing a single source code file."""
    file_path: str = Field(..., description="Absolute or repo-relative path to the file")
    relative_path: str = Field(..., description="Relative path from repository root")
    language: str = Field(..., description="Programming language identifier (e.g. python)")
    size_bytes: int = Field(default=0, description="File size in bytes")
    lines_of_code: int = Field(default=0, description="Total line count")
    extension: str = Field(..., description="File extension")


class CodeSymbol(BaseModel):
    """Base model for any code entity/symbol extracted from source code."""
    symbol_id: str = Field(..., description="Unique deterministic identifier for node identity")
    symbol_name: str = Field(..., description="Name of the symbol")
    symbol_type: SymbolType = Field(..., description="Entity type classification")
    file_path: str = Field(..., description="Relative file path where defined")
    start_line: int = Field(..., description="Start line number in source file")
    end_line: int = Field(..., description="End line number in source file")
    qualified_name: str = Field(..., description="Fully qualified symbol identifier e.g. module.Class.method")
    docstring: str | None = Field(default=None, description="Docstring or doc comment associated with symbol")
    parent_symbol: str | None = Field(default=None, description="Qualified name of enclosing parent symbol if any")


class ClassInfo(CodeSymbol):
    """Model representing a class definition."""
    symbol_type: SymbolType = SymbolType.CLASS
    base_classes: list[str] = Field(default_factory=list, description="List of superclass names")
    methods: list[str] = Field(default_factory=list, description="Qualified names of methods defined in class")
    decorators: list[str] = Field(default_factory=list, description="Decorators applied to class")


class FunctionInfo(CodeSymbol):
    """Model representing a top-level function definition."""
    symbol_type: SymbolType = SymbolType.FUNCTION
    parameters: list[str] = Field(default_factory=list, description="Function parameters")
    return_type: str | None = Field(default=None, description="Annotated return type")
    is_async: bool = Field(default=False, description="Whether the function is async")
    decorators: list[str] = Field(default_factory=list, description="Decorators applied to function")


class MethodInfo(CodeSymbol):
    """Model representing a class method definition."""
    symbol_type: SymbolType = SymbolType.METHOD
    class_name: str = Field(..., description="Name or qualified name of enclosing class")
    parameters: list[str] = Field(default_factory=list, description="Method parameters")
    return_type: str | None = Field(default=None, description="Annotated return type")
    is_async: bool = Field(default=False, description="Whether method is async")
    is_classmethod: bool = Field(default=False, description="True if marked with @classmethod")
    is_staticmethod: bool = Field(default=False, description="True if marked with @staticmethod")
    decorators: list[str] = Field(default_factory=list, description="Decorators applied to method")


class ImportInfo(BaseModel):
    """Model representing an import statement."""
    file_path: str = Field(..., description="Source file containing import")
    module_name: str = Field(..., description="Module being imported")
    imported_symbol: str | None = Field(default=None, description="Specific symbol imported (from X import Y)")
    alias: str | None = Field(default=None, description="Import alias (as Z)")
    line_number: int = Field(..., description="Line number of import statement")


class CallRelation(BaseModel):
    """Model representing a function or method invocation."""
    caller_qualified_name: str = Field(..., description="Qualified name of calling entity")
    callee_name: str = Field(..., description="Name of function/method being called")
    callee_qualified_name: str | None = Field(default=None, description="Resolved qualified name of callee if known")
    line_number: int = Field(..., description="Line number of call site")
    file_path: str = Field(..., description="File path of caller")


class InheritanceRelation(BaseModel):
    """Model representing an inheritance or interface implementation relationship."""
    child_qualified_name: str = Field(..., description="Qualified name of subclass/implementation")
    parent_name: str = Field(..., description="Name of base class/interface")
    parent_qualified_name: str | None = Field(default=None, description="Resolved qualified name of parent class if known")
    file_path: str = Field(..., description="File path containing child definition")
    relationship_type: str = Field(default="INHERITS", description="Relationship type: INHERITS or IMPLEMENTS")


class CodeChunk(BaseModel):
    """Model representing a semantic code snippet for embedding & Qdrant storage."""
    chunk_id: str = Field(..., description="Unique hash/id for vector point")
    repository_id: str = Field(..., description="Repository identifier")
    file_path: str = Field(..., description="File path relative to repo root")
    language: str = Field(default="python", description="Programming language")
    module: str | None = Field(default=None, description="Module name")
    symbol_name: str | None = Field(default=None, description="Associated symbol name")
    symbol_type: str | None = Field(default=None, description="Class/Function/Method/Module")
    start_line: int = Field(..., description="Start line of chunk")
    end_line: int = Field(..., description="End line of chunk")
    content: str = Field(..., description="Source code content snippet")
    parent_symbol: str | None = Field(default=None, description="Parent enclosing symbol qualified name")
    commit_hash: str | None = Field(default=None, description="Commit hash")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional custom metadata")


class ApiEndpoint(BaseModel):
    """Model representing a backend HTTP route endpoint."""

    endpoint_id: str = Field(..., description="Unique deterministic identifier for node")
    repository_id: str = Field(..., description="Repository identifier")
    file_path: str = Field(..., description="File path relative to repo root")
    language: str = Field(default="python", description="Programming language")
    http_method: str = Field(default="GET", description="HTTP Method e.g. GET, POST")
    path: str = Field(..., description="Route path pattern e.g. /api/users/{id}")
    controller_symbol: str = Field(..., description="Qualified name of enclosing controller/handler")
    qualified_name: str = Field(..., description="Unique qualified name e.g. GET:/api/users")
    start_line: int = Field(default=1, description="Start line number")
    end_line: int = Field(default=1, description="End line number")
    framework: str = Field(default="FastAPI", description="Framework e.g. FastAPI, Spring, Express, net/http")
    operation_id: str | None = Field(default=None, description="OpenAPI operationId if known")
    request_schema: str | None = Field(default=None, description="Request body schema if known")
    response_schema: str | None = Field(default=None, description="Response schema if known")


class ApiClientCall(BaseModel):
    """Model representing a frontend or client HTTP request invocation."""

    call_id: str = Field(..., description="Unique deterministic identifier for node")
    repository_id: str = Field(..., description="Repository identifier")
    file_path: str = Field(..., description="File path relative to repo root")
    language: str = Field(default="typescript", description="Programming language")
    http_method: str = Field(default="GET", description="HTTP Method e.g. GET, POST")
    url: str = Field(..., description="Target URL path or template e.g. /api/users")
    base_url: str = Field(default="", description="Base URL prefix if statically known")
    client_symbol: str = Field(..., description="Enclosing symbol/function making call")
    start_line: int = Field(default=1, description="Start line number")
    end_line: int = Field(default=1, description="End line number")


class ApiContract(BaseModel):
    """Model representing an OpenAPI specification contract endpoint."""

    contract_id: str = Field(..., description="Unique deterministic identifier for contract")
    repository_id: str = Field(..., description="Repository identifier")
    file_path: str = Field(..., description="Path to openapi.yaml/json file")
    operation_id: str | None = Field(default=None, description="OpenAPI operationId")
    http_method: str = Field(default="GET", description="HTTP method")
    path_template: str = Field(..., description="Path template e.g. /api/users/{id}")
    summary: str | None = Field(default=None, description="Operation summary")
    schemas: dict[str, Any] = Field(default_factory=dict, description="Associated JSON schemas")


class ApiMatch(BaseModel):
    """Model representing a verified relationship between API client, endpoint, or contract."""

    source_id: str = Field(..., description="Source node ID (ApiClientCall or ApiEndpoint)")
    target_id: str = Field(..., description="Target node ID (ApiEndpoint or ApiContract)")
    match_reason: str = Field(..., description="Evidence basis: EXACT_METHOD_AND_PATH, PATH_TEMPLATE_MATCH, etc.")
    confidence_basis: str = Field(default="static_evidence", description="Explanation of match basis")
    file_path: str = Field(default="", description="File path of client call")
    line_number: int = Field(default=1, description="Line number of client call site")


class ApiLinkResult(BaseModel):
    """Aggregated container of cross-language API extraction and matching data."""

    endpoints: list[ApiEndpoint] = Field(default_factory=list)
    client_calls: list[ApiClientCall] = Field(default_factory=list)
    contracts: list[ApiContract] = Field(default_factory=list)
    matches: list[ApiMatch] = Field(default_factory=list)


class ExtractedCodeData(BaseModel):
    """Aggregated container of all code elements extracted from a repository file or module."""

    repository_id: str
    file_info: SourceFile
    symbols: list[CodeSymbol] = Field(default_factory=list)
    imports: list[ImportInfo] = Field(default_factory=list)
    calls: list[CallRelation] = Field(default_factory=list)
    inheritance: list[InheritanceRelation] = Field(default_factory=list)
    chunks: list[CodeChunk] = Field(default_factory=list)
    api_endpoints: list[ApiEndpoint] = Field(default_factory=list)
    api_client_calls: list[ApiClientCall] = Field(default_factory=list)
    api_contracts: list[ApiContract] = Field(default_factory=list)


class QueryAnalysisResult(BaseModel):
    """Structured result of natural language query analysis."""

    query: str
    intent: str
    candidate_symbols: list[str] = Field(default_factory=list)
    candidate_files: list[str] = Field(default_factory=list)
    requested_hops: int = 2
    repository_id: str | None = None


class ResolvedEntity(BaseModel):
    """Code entity resolved from database matching query candidate terms."""

    symbol_id: str
    name: str
    qualified_name: str
    symbol_type: str
    file_path: str = "unknown"
    start_line: int | None = None
    end_line: int | None = None
    match_type: str = "exact"
    confidence: float = 1.0


class GraphNode(BaseModel):
    """Normalized representation of a node in the software graph."""

    id: str
    name: str
    qualified_name: str | None = None
    labels: list[str] = Field(default_factory=list)
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    docstring: str | None = None


class GraphRelationship(BaseModel):
    """Normalized representation of an edge in the software graph."""

    source_id: str
    target_id: str
    relationship_type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphPath(BaseModel):
    """Structured multi-hop path representation between code components."""

    source_node: GraphNode
    target_node: GraphNode
    relationships: list[str] = Field(default_factory=list)
    hop_count: int = 1
    path_sequence: list[str] = Field(default_factory=list)


class NormalizedSearchResult(BaseModel):
    """Normalized search item produced by graph or semantic retrieval before/after RRF fusion."""

    id: str
    source: str = "semantic"  # "graph", "semantic", or "both"
    repository_id: str
    file_path: str
    symbol_name: str | None = None
    qualified_name: str | None = None
    symbol_type: str | None = None
    start_line: int = 1
    end_line: int = 1
    content: str
    score: float = 0.0
    rrf_score: float = 0.0
    path_info: str | None = None


class GraphRAGResponse(BaseModel):
    """Final grounded response object from Graph RAG reasoning pipeline."""

    answer: str
    repository_id: str | None = None
    query: str
    intent: str | None = None
    sources: list[str] = Field(default_factory=list)
    graph_paths: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_summary: str | None = None
    confidence: float = 0.8
    validation_status: bool = True
    debug_info: dict[str, Any] | None = None


class ImpactNode(BaseModel):
    """Structured representation of an impacted code node."""

    symbol_id: str
    name: str = "Unknown"
    qualified_name: str = "Unknown"
    symbol_type: str = "Symbol"
    file_path: str = "unknown"
    start_line: int | None = None
    end_line: int | None = None
    relationship_type: str = "DEPENDS_ON"
    hop_count: int = 1
    impact_category: str = "direct_dependent"  # direct_dependent, transitive_dependent, direct_dependency, etc.


class ImpactPath(BaseModel):
    """Structured graph path representing dependency impact propagation."""

    source_symbol: str
    target_symbol: str
    hop_count: int = 1
    path_sequence: list[str] = Field(default_factory=list)
    file_paths: list[str] = Field(default_factory=list)


class ImpactSummary(BaseModel):
    """Aggregated structural impact indicators and measurements."""

    direct_dependents_count: int = 0
    transitive_dependents_count: int = 0
    direct_dependencies_count: int = 0
    transitive_dependencies_count: int = 0
    affected_files_count: int = 0
    affected_symbols_count: int = 0
    max_hops_used: int | str = 2
    analysis_truncated: bool = False


class ImpactAnalysisRequest(BaseModel):
    """Request parameters for code impact analysis."""

    symbol: str = Field(..., description="Target symbol name, qualified name, or file+symbol")
    repository_id: str | None = Field(None, description="Optional target repository identifier")
    max_hops: int | str = Field(2, description="Maximum traversal depth (1, 2, 3, or 'all')")
    max_nodes: int = Field(50, description="Maximum total nodes to evaluate")
    max_relationships: int = Field(100, description="Maximum relationships to traverse")


class ImpactAnalysisResult(BaseModel):
    """Complete structured result returned by Code Impact Analysis Engine."""

    target: ResolvedEntity
    summary: ImpactSummary
    direct_dependencies: list[ImpactNode] = Field(default_factory=list)
    direct_dependents: list[ImpactNode] = Field(default_factory=list)
    transitive_dependencies: list[ImpactNode] = Field(default_factory=list)
    transitive_dependents: list[ImpactNode] = Field(default_factory=list)
    impact_paths: list[ImpactPath] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    evidence_snippets: list[NormalizedSearchResult] = Field(default_factory=list)
    explanation: str
    analysis_truncated: bool = False


