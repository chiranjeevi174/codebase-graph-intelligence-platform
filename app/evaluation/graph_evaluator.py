"""Evaluator for multi-hop graph paths and structural relationships."""

from app.evaluation.metrics import path_accuracy
from app.evaluation.models import EvalCase, MultiHopReasoningReport
from app.models.entities import GraphPath


class GraphEvaluator:
    """Evaluates multi-hop graph reasoning accuracy."""

    def evaluate_paths(self, retrieved_paths: list[GraphPath], case: EvalCase) -> dict[str, float]:
        """Evaluate actual retrieved graph paths against expected paths."""
        act_sequences = []
        for p in retrieved_paths:
            seq = p.path_sequence or [p.source_node.name, p.target_node.name]
            act_sequences.append(seq)

        return path_accuracy(act_sequences, case.expected_paths)

    def evaluate_dataset(self, cases: list[EvalCase], all_paths: list[list[GraphPath]]) -> MultiHopReasoningReport:
        """Evaluate multi-hop path accuracy across all benchmark test cases."""
        if not cases or len(cases) != len(all_paths):
            return MultiHopReasoningReport()

        found_sum = 0.0
        acc_sum = 0.0
        rel_sum = 0.0
        evaluated_cases = 0

        for case, paths in zip(cases, all_paths):
            if case.expected_paths:
                res = self.evaluate_paths(paths, case)
                found_sum += res["path_found"]
                acc_sum += res["path_accuracy"]
                rel_sum += res["relationship_accuracy"]
                evaluated_cases += 1

        if evaluated_cases == 0:
            return MultiHopReasoningReport(
                path_found_rate=1.0, path_accuracy=1.0, relationship_accuracy=1.0, node_coverage=1.0
            )

        return MultiHopReasoningReport(
            path_found_rate=found_sum / evaluated_cases,
            path_accuracy=acc_sum / evaluated_cases,
            relationship_accuracy=rel_sum / evaluated_cases,
            node_coverage=acc_sum / evaluated_cases,
        )
