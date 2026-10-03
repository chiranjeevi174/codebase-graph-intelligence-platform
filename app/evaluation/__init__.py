"""Evaluation framework module exports."""

from app.evaluation.answer_evaluator import AnswerEvaluator
from app.evaluation.dataset_loader import load_evaluation_dataset
from app.evaluation.evaluation_runner import EvaluationRunner
from app.evaluation.graph_evaluator import GraphEvaluator
from app.evaluation.latency_tracker import LatencyTracker
from app.evaluation.metrics import (
    answer_completeness,
    citation_metrics,
    compute_metric_set,
    entity_resolution_metrics,
    hit_at_k,
    mrr_at_k,
    path_accuracy,
    recall_at_k,
)
from app.evaluation.models import (
    AnswerQualityReport,
    BenchmarkConfig,
    BenchmarkReport,
    EntityResolutionReport,
    EvalCase,
    FailureCategory,
    FailureRecord,
    LatencyStats,
    MetricSet,
    MultiHopReasoningReport,
    ReproducibilityMetadata,
    RetrievalComparisonReport,
)
from app.evaluation.report_generator import ReportGenerator
from app.evaluation.retrieval_evaluator import RetrievalEvaluator

__all__ = [
    "AnswerEvaluator",
    "AnswerQualityReport",
    "BenchmarkConfig",
    "BenchmarkReport",
    "EntityResolutionReport",
    "EvalCase",
    "EvaluationRunner",
    "FailureCategory",
    "FailureRecord",
    "GraphEvaluator",
    "LatencyStats",
    "LatencyTracker",
    "MetricSet",
    "MultiHopReasoningReport",
    "ReportGenerator",
    "ReproducibilityMetadata",
    "RetrievalComparisonReport",
    "RetrievalEvaluator",
    "answer_completeness",
    "citation_metrics",
    "compute_metric_set",
    "entity_resolution_metrics",
    "hit_at_k",
    "load_evaluation_dataset",
    "mrr_at_k",
    "path_accuracy",
    "recall_at_k",
]
