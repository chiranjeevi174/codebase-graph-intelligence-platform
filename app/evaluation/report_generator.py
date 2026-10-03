"""Report generator writing machine-readable JSON and human-readable Markdown evaluation summaries."""

import json
from pathlib import Path

from app.evaluation.models import BenchmarkReport


class ReportGenerator:
    """Formats and writes benchmark evaluation reports."""

    def __init__(self, output_dir: str | Path = "data/evaluation/results"):
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_report(self, report: BenchmarkReport) -> dict[str, str]:
        """Save machine-readable JSON reports and Markdown summary file.

        Returns dictionary of file paths created.
        """
        saved_files = {}

        # 1. Main JSON report
        main_json_path = self.output_dir / "evaluation_report.json"
        with open(main_json_path, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, indent=2)
        saved_files["main_report"] = str(main_json_path)

        # 2. Separate metric JSONs
        retrieval_json_path = self.output_dir / "retrieval_metrics.json"
        with open(retrieval_json_path, "w", encoding="utf-8") as f:
            json.dump(report.retrieval_comparison.model_dump(), f, indent=2)
        saved_files["retrieval_metrics"] = str(retrieval_json_path)

        reasoning_json_path = self.output_dir / "reasoning_metrics.json"
        with open(reasoning_json_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "entity_resolution": report.entity_resolution.model_dump(),
                    "multi_hop_reasoning": report.multi_hop_reasoning.model_dump(),
                },
                f,
                indent=2,
            )
        saved_files["reasoning_metrics"] = str(reasoning_json_path)

        answer_json_path = self.output_dir / "answer_metrics.json"
        with open(answer_json_path, "w", encoding="utf-8") as f:
            json.dump(report.answer_quality.model_dump(), f, indent=2)
        saved_files["answer_metrics"] = str(answer_json_path)

        latency_json_path = self.output_dir / "latency_metrics.json"
        with open(latency_json_path, "w", encoding="utf-8") as f:
            json.dump(report.latency.model_dump(), f, indent=2)
        saved_files["latency_metrics"] = str(latency_json_path)

        # 3. Markdown Summary
        md_path = self.output_dir / "evaluation_summary.md"
        md_content = self._generate_markdown_summary(report)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        saved_files["markdown_summary"] = str(md_path)

        return saved_files

    def _generate_markdown_summary(self, report: BenchmarkReport) -> str:
        r = report.retrieval_comparison
        e = report.entity_resolution
        m = report.multi_hop_reasoning
        a = report.answer_quality
        lat = report.latency
        meta = report.metadata

        lines = [
            "# Graph RAG Evaluation & Benchmark Report",
            "",
            f"**Timestamp:** {meta.timestamp}  ",
            f"**Total Cases Evaluated:** {report.total_cases_evaluated}  ",
            f"**Embedding Model:** `{meta.embedding_model}`  ",
            f"**LLM Provider:** `{meta.llm_provider}`  ",
            "",
            "## 1. Retrieval Mode Comparison (Graph vs. Semantic vs. Hybrid RRF)",
            "",
            "| Metric | Graph Only | Semantic Only | Hybrid + RRF |",
            "| :--- | :---: | :---: | :---: |",
            f"| **Hit@1** | {r.graph_only.hit_at_1:.3f} | {r.semantic_only.hit_at_1:.3f} | {r.hybrid_rrf.hit_at_1:.3f} |",
            f"| **Hit@3** | {r.graph_only.hit_at_3:.3f} | {r.semantic_only.hit_at_3:.3f} | {r.hybrid_rrf.hit_at_3:.3f} |",
            f"| **Hit@5** | {r.graph_only.hit_at_5:.3f} | {r.semantic_only.hit_at_5:.3f} | {r.hybrid_rrf.hit_at_5:.3f} |",
            f"| **Hit@10** | {r.graph_only.hit_at_10:.3f} | {r.semantic_only.hit_at_10:.3f} | {r.hybrid_rrf.hit_at_10:.3f} |",
            f"| **Recall@5** | {r.graph_only.recall_at_5:.3f} | {r.semantic_only.recall_at_5:.3f} | {r.hybrid_rrf.recall_at_5:.3f} |",
            f"| **Recall@10** | {r.graph_only.recall_at_10:.3f} | {r.semantic_only.recall_at_10:.3f} | {r.hybrid_rrf.recall_at_10:.3f} |",
            f"| **MRR@5** | {r.graph_only.mrr_at_5:.3f} | {r.semantic_only.mrr_at_5:.3f} | {r.hybrid_rrf.mrr_at_5:.3f} |",
            f"| **MRR@10** | {r.graph_only.mrr_at_10:.3f} | {r.semantic_only.mrr_at_10:.3f} | {r.hybrid_rrf.mrr_at_10:.3f} |",
            "",
            "## 2. Entity Resolution & Multi-Hop Reasoning",
            "",
            "| Metric | Measured Score |",
            "| :--- | :---: |",
            f"| Entity Resolution Accuracy | {e.accuracy * 100:.1f}% |",
            f"| Entity Resolution Precision | {e.precision * 100:.1f}% |",
            f"| Entity Resolution Recall | {e.recall * 100:.1f}% |",
            f"| Multi-Hop Path Found Rate | {m.path_found_rate * 100:.1f}% |",
            f"| Multi-Hop Path Accuracy | {m.path_accuracy * 100:.1f}% |",
            f"| Relationship Accuracy | {m.relationship_accuracy * 100:.1f}% |",
            "",
            "## 3. Answer Quality & Citation Accuracy",
            "",
            "| Metric | Measured Score |",
            "| :--- | :---: |",
            f"| Grounded Answer Rate | {a.groundedness_rate * 100:.1f}% |",
            f"| Citation Precision | {a.citation_precision * 100:.1f}% |",
            f"| Citation Recall | {a.citation_recall * 100:.1f}% |",
            f"| Answer Completeness | {a.answer_completeness * 100:.1f}% |",
            "",
            "## 4. Execution Latency Breakdown",
            "",
            "| Pipeline Stage | Mean Latency (s) |",
            "| :--- | :---: |",
            f"| Query Analysis | {lat.query_analysis_mean:.4f} s |",
            f"| Entity Resolution | {lat.entity_resolution_mean:.4f} s |",
            f"| Graph Retrieval | {lat.graph_retrieval_mean:.4f} s |",
            f"| Semantic Retrieval | {lat.semantic_retrieval_mean:.4f} s |",
            f"| RRF Fusion | {lat.rrf_fusion_mean:.4f} s |",
            f"| Subgraph Construction | {lat.subgraph_construction_mean:.4f} s |",
            f"| Context Fusion | {lat.context_fusion_mean:.4f} s |",
            f"| LLM Answer Generation | {lat.llm_generation_mean:.4f} s |",
            f"| Answer Validation | {lat.validation_mean:.4f} s |",
            f"| **Total Pipeline (Mean)** | **{lat.total_pipeline_mean:.4f} s** |",
            f"| **Total Pipeline (Median)** | **{lat.total_pipeline_median:.4f} s** |",
            f"| **Total Pipeline (p95)** | **{lat.total_pipeline_p95:.4f} s** |",
            "",
            "## 5. Failure Analysis",
            "",
            f"Total Failure Records: `{len(report.failures)}`",
            "",
        ]

        if report.failures:
            lines.append("| Case ID | Category | Question | Details |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for f in report.failures[:10]:
                q_short = f.question[:40] + "..." if len(f.question) > 40 else f.question
                lines.append(f"| {f.case_id} | {f.failure_category.value} | {q_short} | {f.details} |")

        return "\n".join(lines)
