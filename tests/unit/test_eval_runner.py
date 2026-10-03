"""Unit tests for LatencyTracker and ReportGenerator."""

from pathlib import Path
from tempfile import TemporaryDirectory
import pytest

from app.evaluation.latency_tracker import LatencyTracker
from app.evaluation.models import (
    AnswerQualityReport,
    BenchmarkReport,
    EntityResolutionReport,
    MetricSet,
    MultiHopReasoningReport,
    ReproducibilityMetadata,
    RetrievalComparisonReport,
)
from app.evaluation.report_generator import ReportGenerator


def test_latency_tracker():
    tracker = LatencyTracker()
    tracker.record_run({"total": 1.0, "query_analysis": 0.1})
    tracker.record_run({"total": 2.0, "query_analysis": 0.2})

    stats = tracker.compute_stats()
    assert stats.total_pipeline_mean == 1.5
    assert stats.total_pipeline_median == 1.5
    assert pytest.approx(stats.query_analysis_mean) == 0.15


def test_report_generator():
    with TemporaryDirectory() as tmp_dir:
        gen = ReportGenerator(output_dir=tmp_dir)
        m = MetricSet(hit_at_5=1.0)
        report = BenchmarkReport(
            metadata=ReproducibilityMetadata(timestamp="2026-10-02T12:00:00Z"),
            total_cases_evaluated=1,
            retrieval_comparison=RetrievalComparisonReport(graph_only=m, semantic_only=m, hybrid_rrf=m),
            entity_resolution=EntityResolutionReport(),
            multi_hop_reasoning=MultiHopReasoningReport(),
            answer_quality=AnswerQualityReport(),
            latency=tracker_stats(),
        )

        files = gen.save_report(report)
        assert Path(files["main_report"]).exists()
        assert Path(files["markdown_summary"]).exists()


def tracker_stats():
    tracker = LatencyTracker()
    tracker.record_run({"total": 1.0})
    return tracker.compute_stats()
