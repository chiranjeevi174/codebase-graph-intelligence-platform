"""Evaluator for comparative Graph, Semantic, and Hybrid RRF retrieval performance."""

from app.evaluation.metrics import compute_metric_set
from app.evaluation.models import EvalCase, MetricSet, RetrievalComparisonReport
from app.graph.graph_queries import GraphQueryManager
from app.models.entities import NormalizedSearchResult
from app.retrieval.rrf import RRFComposer
from app.retrieval.semantic_retriever import SemanticRetriever


class RetrievalEvaluator:
    """Evaluates and compares standalone Graph, Semantic, and Hybrid RRF retrieval."""

    def __init__(
        self,
        graph_qm: GraphQueryManager | None = None,
        semantic_retriever: SemanticRetriever | None = None,
    ):
        self.graph_qm = graph_qm or GraphQueryManager()
        self.semantic_retriever = semantic_retriever or SemanticRetriever()
        self.rrf_composer = RRFComposer(k=60)

    def evaluate_case(self, case: EvalCase) -> dict[str, list[str]]:
        """Perform Graph, Semantic, and Hybrid RRF retrieval for a single test case.

        Returns dictionary of extracted entity strings for each mode.
        """
        # 1. Graph Only Retrieval
        graph_entities: list[str] = []
        seen_g: set[str] = set()
        for symbol in case.target_symbols:
            records = self.graph_qm.find_symbol(symbol)
            records.extend(self.graph_qm.find_callers(symbol))
            records.extend(self.graph_qm.find_callees(symbol))
            for r in records:
                qn = r.get("qualified_name") or r.get("name") or r.get("caller_name") or r.get("callee_name")
                fpath = r.get("file_path")
                if qn and qn not in seen_g:
                    seen_g.add(qn)
                    graph_entities.append(qn)
                if fpath and fpath not in seen_g:
                    seen_g.add(fpath)
                    graph_entities.append(fpath)

        # 2. Semantic Only Retrieval
        semantic_results = self.semantic_retriever.retrieve(
            query=case.question,
            limit=10,
            repository_id=case.repository_id,
        )
        semantic_entities: list[str] = []
        for sem in semantic_results:
            if sem.qualified_name:
                semantic_entities.append(sem.qualified_name)
            elif sem.symbol_name:
                semantic_entities.append(sem.symbol_name)
            if sem.file_path:
                semantic_entities.append(sem.file_path)

        # 3. Hybrid RRF Retrieval
        graph_norm_results = [
            NormalizedSearchResult(
                id=f"g_{idx}",
                source="graph",
                repository_id=case.repository_id,
                file_path=item,
                symbol_name=item,
                qualified_name=item,
                content=item,
            )
            for idx, item in enumerate(graph_entities)
        ]

        fused = self.rrf_composer.fuse(
            graph_results=graph_norm_results,
            semantic_results=semantic_results,
            top_k=10,
        )
        hybrid_entities: list[str] = []
        for f in fused:
            if f.qualified_name:
                hybrid_entities.append(f.qualified_name)
            elif f.symbol_name:
                hybrid_entities.append(f.symbol_name)
            if f.file_path:
                hybrid_entities.append(f.file_path)

        return {
            "graph": graph_entities,
            "semantic": semantic_entities,
            "hybrid": hybrid_entities,
        }

    def evaluate_dataset(self, cases: list[EvalCase]) -> RetrievalComparisonReport:
        """Evaluate retrieval across all dataset test cases and average metrics."""
        if not cases:
            empty = MetricSet()
            return RetrievalComparisonReport(graph_only=empty, semantic_only=empty, hybrid_rrf=empty)

        graph_metrics_list: list[MetricSet] = []
        semantic_metrics_list: list[MetricSet] = []
        hybrid_metrics_list: list[MetricSet] = []

        for case in cases:
            expected = case.expected_entities + case.expected_files
            res = self.evaluate_case(case)

            graph_metrics_list.append(compute_metric_set(res["graph"], expected))
            semantic_metrics_list.append(compute_metric_set(res["semantic"], expected))
            hybrid_metrics_list.append(compute_metric_set(res["hybrid"], expected))

        def average_metrics(m_list: list[MetricSet]) -> MetricSet:
            n = len(m_list)
            if n == 0:
                return MetricSet()
            return MetricSet(
                hit_at_1=sum(m.hit_at_1 for m in m_list) / n,
                hit_at_3=sum(m.hit_at_3 for m in m_list) / n,
                hit_at_5=sum(m.hit_at_5 for m in m_list) / n,
                hit_at_10=sum(m.hit_at_10 for m in m_list) / n,
                recall_at_1=sum(m.recall_at_1 for m in m_list) / n,
                recall_at_3=sum(m.recall_at_3 for m in m_list) / n,
                recall_at_5=sum(m.recall_at_5 for m in m_list) / n,
                recall_at_10=sum(m.recall_at_10 for m in m_list) / n,
                mrr_at_1=sum(m.mrr_at_1 for m in m_list) / n,
                mrr_at_3=sum(m.mrr_at_3 for m in m_list) / n,
                mrr_at_5=sum(m.mrr_at_5 for m in m_list) / n,
                mrr_at_10=sum(m.mrr_at_10 for m in m_list) / n,
            )

        return RetrievalComparisonReport(
            graph_only=average_metrics(graph_metrics_list),
            semantic_only=average_metrics(semantic_metrics_list),
            hybrid_rrf=average_metrics(hybrid_metrics_list),
        )
