"""Latency tracker for measuring stage-by-stage execution times."""

import statistics
import time
from typing import Any

from app.evaluation.models import LatencyStats


class LatencyTracker:
    """Tracks latency for each pipeline stage and computes summary statistics."""

    def __init__(self):
        self.records: list[dict[str, float]] = []

    def record_run(self, stage_times: dict[str, float]):
        """Record stage execution times (in seconds) for a single run."""
        self.records.append(stage_times)

    def compute_stats(self) -> LatencyStats:
        """Compute aggregated mean, median, and p95 latency statistics."""
        if not self.records:
            return LatencyStats()

        def mean_key(key: str) -> float:
            vals = [r.get(key, 0.0) for r in self.records]
            return statistics.mean(vals) if vals else 0.0

        totals = [r.get("total", 0.0) for r in self.records]
        total_mean = statistics.mean(totals) if totals else 0.0
        total_median = statistics.median(totals) if totals else 0.0

        if len(totals) >= 2:
            totals_sorted = sorted(totals)
            p95_idx = int(0.95 * (len(totals_sorted) - 1))
            total_p95 = totals_sorted[p95_idx]
        else:
            total_p95 = total_mean

        return LatencyStats(
            query_analysis_mean=mean_key("query_analysis"),
            entity_resolution_mean=mean_key("entity_resolution"),
            graph_retrieval_mean=mean_key("graph_retrieval"),
            semantic_retrieval_mean=mean_key("semantic_retrieval"),
            rrf_fusion_mean=mean_key("rrf_fusion"),
            subgraph_construction_mean=mean_key("subgraph_construction"),
            context_fusion_mean=mean_key("context_fusion"),
            llm_generation_mean=mean_key("llm_generation"),
            validation_mean=mean_key("validation"),
            total_pipeline_mean=total_mean,
            total_pipeline_median=total_median,
            total_pipeline_p95=total_p95,
        )
