"""Pydantic models for evaluation framework, metrics, and report structures."""

from enum import Enum

from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    ENTITY_RESOLUTION = "ENTITY_RESOLUTION"
    GRAPH_RETRIEVAL = "GRAPH_RETRIEVAL"
    SEMANTIC_RETRIEVAL = "SEMANTIC_RETRIEVAL"
    RRF_FUSION = "RRF_FUSION"
    MULTI_HOP = "MULTI_HOP"
    CONTEXT_FUSION = "CONTEXT_FUSION"
    ANSWER_GENERATION = "ANSWER_GENERATION"
    CITATION = "CITATION"
    VALIDATION = "VALIDATION"


class EvalCase(BaseModel):
    """Single benchmark evaluation test case."""

    case_id: str
    repository_id: str
    question: str
    intent: str = "general_code_question"
    category: str = "general_code_question"
    language: str = "python"
    difficulty: str = "medium"
    target_symbols: list[str] = Field(default_factory=list)
    expected_entities: list[str] = Field(default_factory=list)
    expected_relationships: list[str] = Field(default_factory=list)
    expected_paths: list[list[str]] = Field(default_factory=list)
    expected_files: list[str] = Field(default_factory=list)
    expected_line_ranges: list[list[int]] = Field(default_factory=list)
    expected_answer_keywords: list[str] = Field(default_factory=list)


class BenchmarkConfig(BaseModel):
    """Configuration parameters for evaluation benchmark run."""

    k_values: list[int] = Field(default_factory=lambda: [1, 3, 5, 10])
    max_hops: int = 2
    dataset_path: str = "data/evaluation/codebase_questions.jsonl"
    repository_id: str | None = None


class MetricSet(BaseModel):
    """Retrieval performance metrics across K values."""

    hit_at_1: float = 0.0
    hit_at_3: float = 0.0
    hit_at_5: float = 0.0
    hit_at_10: float = 0.0
    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    mrr_at_1: float = 0.0
    mrr_at_3: float = 0.0
    mrr_at_5: float = 0.0
    mrr_at_10: float = 0.0


class RetrievalComparisonReport(BaseModel):
    """Comparative retrieval performance metrics for Graph, Semantic, and Hybrid RRF."""

    graph_only: MetricSet
    semantic_only: MetricSet
    hybrid_rrf: MetricSet


class EntityResolutionReport(BaseModel):
    """Entity resolution accuracy, precision, and recall metrics."""

    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    exact_matches: int = 0
    total_cases: int = 0


class MultiHopReasoningReport(BaseModel):
    """Multi-hop path and graph structure evaluation metrics."""

    path_found_rate: float = 0.0
    path_accuracy: float = 0.0
    relationship_accuracy: float = 0.0
    node_coverage: float = 0.0


class AnswerQualityReport(BaseModel):
    """Answer grounding, citation, and completeness metrics."""

    groundedness_rate: float = 0.0
    citation_precision: float = 0.0
    citation_recall: float = 0.0
    answer_completeness: float = 0.0


class LatencyStats(BaseModel):
    """Detailed stage-by-stage latency measurements (in seconds)."""

    query_analysis_mean: float = 0.0
    entity_resolution_mean: float = 0.0
    graph_retrieval_mean: float = 0.0
    semantic_retrieval_mean: float = 0.0
    rrf_fusion_mean: float = 0.0
    subgraph_construction_mean: float = 0.0
    context_fusion_mean: float = 0.0
    llm_generation_mean: float = 0.0
    validation_mean: float = 0.0
    total_pipeline_mean: float = 0.0
    total_pipeline_median: float = 0.0
    total_pipeline_p95: float = 0.0


class FailureRecord(BaseModel):
    """Recorded benchmark case failure for engineering diagnostic analysis."""

    case_id: str
    question: str
    repository_id: str
    failure_category: FailureCategory
    expected_entities: list[str] = Field(default_factory=list)
    retrieved_entities: list[str] = Field(default_factory=list)
    details: str = ""


class ReproducibilityMetadata(BaseModel):
    """Metadata tracking configuration parameters for reproducible evaluation runs."""

    timestamp: str
    commit_hash: str | None = None
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    llm_provider: str = "openai"
    dataset_version: str = "1.0"
    k_values: list[int] = Field(default_factory=lambda: [1, 3, 5, 10])
    max_hops: int = 2


class BenchmarkReport(BaseModel):
    """Complete aggregated evaluation benchmark report."""

    metadata: ReproducibilityMetadata
    total_cases_evaluated: int = 0
    retrieval_comparison: RetrievalComparisonReport
    entity_resolution: EntityResolutionReport
    multi_hop_reasoning: MultiHopReasoningReport
    answer_quality: AnswerQualityReport
    latency: LatencyStats
    failures: list[FailureRecord] = Field(default_factory=list)
    category_breakdown: dict[str, dict[str, float]] = Field(default_factory=dict)
