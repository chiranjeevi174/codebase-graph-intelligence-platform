"""Evaluator for generated answer quality, grounding, citations, and completeness."""

import re

from app.evaluation.metrics import answer_completeness, citation_metrics
from app.evaluation.models import AnswerQualityReport, EvalCase
from app.models.entities import GraphRAGResponse


class AnswerEvaluator:
    """Evaluates answer grounding, citations, and content completeness."""

    def extract_citations_from_text(self, text: str) -> list[str]:
        """Extract cited file paths from generated answer markdown text."""
        # Regex for backticked paths like `src/app.py:10-20` or `com/example/Main.java`
        matches = re.findall(r"`([a-zA-Z0-9_\-/\\]+\.[a-zA-Z0-9]+)(?::\d+-\d+)?`", text)
        return list(set(matches))

    def evaluate_response(self, response: GraphRAGResponse, case: EvalCase) -> dict[str, float]:
        """Evaluate a single GraphRAG response against expected case criteria."""
        citations = self.extract_citations_from_text(response.answer)
        if not citations and response.sources:
            citations = response.sources

        c_metrics = citation_metrics(citations, case.expected_files)
        completeness = answer_completeness(response.answer, case.expected_answer_keywords)

        return {
            "groundedness": 1.0 if response.validation_status else 0.0,
            "citation_precision": c_metrics["precision"],
            "citation_recall": c_metrics["recall"],
            "completeness": completeness,
        }

    def evaluate_dataset(self, cases: list[EvalCase], responses: list[GraphRAGResponse]) -> AnswerQualityReport:
        """Aggregate answer evaluation metrics across dataset responses."""
        if not cases or len(cases) != len(responses):
            return AnswerQualityReport()

        n = len(cases)
        grounded_sum = 0.0
        prec_sum = 0.0
        rec_sum = 0.0
        comp_sum = 0.0

        for case, resp in zip(cases, responses):
            res = self.evaluate_response(resp, case)
            grounded_sum += res["groundedness"]
            prec_sum += res["citation_precision"]
            rec_sum += res["citation_recall"]
            comp_sum += res["completeness"]

        return AnswerQualityReport(
            groundedness_rate=grounded_sum / n,
            citation_precision=prec_sum / n,
            citation_recall=rec_sum / n,
            answer_completeness=comp_sum / n,
        )
