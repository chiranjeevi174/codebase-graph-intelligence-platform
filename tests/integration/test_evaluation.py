"""Integration test for end-to-end evaluation benchmark framework."""

from pathlib import Path

import pytest

from app.evaluation.evaluation_runner import EvaluationRunner
from app.evaluation.models import BenchmarkReport


@pytest.mark.integration
def test_evaluation_benchmark_run():
    dataset_path = Path("data/evaluation/codebase_questions.jsonl").resolve()
    assert dataset_path.exists(), f"Dataset path {dataset_path} must exist"

    output_dir = Path("data/evaluation/results_test").resolve()

    runner = EvaluationRunner(output_dir=str(output_dir))
    report: BenchmarkReport = runner.run_benchmark(
        dataset_path=str(dataset_path),
        repository_id="sample_repo",
        k_values=[1, 3, 5, 10],
    )

    # 1. Assert benchmark completion and case count
    assert report.total_cases_evaluated >= 10
    assert report.retrieval_comparison.hybrid_rrf.hit_at_5 > 0.0

    # 2. Assert metrics computed
    assert report.entity_resolution.accuracy > 0.0
    assert report.latency.total_pipeline_mean > 0.0

    # 3. Assert report files written
    assert (output_dir / "evaluation_report.json").exists()
    assert (output_dir / "retrieval_metrics.json").exists()
    assert (output_dir / "reasoning_metrics.json").exists()
    assert (output_dir / "answer_metrics.json").exists()
    assert (output_dir / "latency_metrics.json").exists()
    assert (output_dir / "evaluation_summary.md").exists()
