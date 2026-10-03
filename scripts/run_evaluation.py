"""CLI script for executing Graph RAG benchmark evaluation suite."""

import argparse
import sys
from pathlib import Path

# Add project root directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.evaluation.evaluation_runner import EvaluationRunner
from app.utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description="Graph RAG Evaluation & Benchmarking Runner")
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/evaluation/codebase_questions.jsonl",
        help="Path to evaluation questions dataset JSONL file",
    )
    parser.add_argument(
        "--repository",
        type=str,
        default=None,
        help="Optional repository_id filter (e.g. sample_repo, multi_language_repo)",
    )
    parser.add_argument(
        "--k",
        type=str,
        default="1,3,5,10",
        help="Comma-separated K values for retrieval evaluation (e.g. 1,3,5,10)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/evaluation/results",
        help="Directory path to save evaluation JSON reports and markdown summary",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging",
    )

    args = parser.parse_args()

    k_values = [int(x.strip()) for x in args.k.split(",") if x.strip().isdigit()]

    logger.info("==================================================")
    logger.info(" GRAPH RAG EVALUATION BENCHMARK RUNNER")
    logger.info("==================================================")
    logger.info(f"Dataset:       {args.dataset}")
    logger.info(f"Repository:    {args.repository or 'ALL'}")
    logger.info(f"K Values:      {k_values}")
    logger.info(f"Output Dir:    {args.output_dir}")
    logger.info("==================================================")

    runner = EvaluationRunner(output_dir=args.output_dir)
    report = runner.run_benchmark(
        dataset_path=args.dataset,
        repository_id=args.repository,
        k_values=k_values,
    )

    print("\n==================================================")
    print(" EVALUATION COMPLETED")
    print("==================================================")
    print(f"Total Cases Evaluated:   {report.total_cases_evaluated}")
    print(f"Graph Only Hit@5:         {report.retrieval_comparison.graph_only.hit_at_5:.3f}")
    print(f"Semantic Only Hit@5:      {report.retrieval_comparison.semantic_only.hit_at_5:.3f}")
    print(f"Hybrid RRF Hit@5:         {report.retrieval_comparison.hybrid_rrf.hit_at_5:.3f}")
    print(f"Entity Resolution Acc:   {report.entity_resolution.accuracy * 100:.1f}%")
    print(f"Multi-Hop Path Acc:      {report.multi_hop_reasoning.path_accuracy * 100:.1f}%")
    print(f"Grounded Answer Rate:    {report.answer_quality.groundedness_rate * 100:.1f}%")
    print(f"Mean Pipeline Latency:   {report.latency.total_pipeline_mean:.4f} s")
    print("==================================================\n")


if __name__ == "__main__":
    main()
