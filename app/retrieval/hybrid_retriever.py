"""Hybrid Retriever unifying Neo4j graph retrieval, Qdrant semantic search, and RRF fusion."""

from typing import Any

from app.graph.graph_queries import GraphQueryManager
from app.models.entities import NormalizedSearchResult, QueryAnalysisResult, ResolvedEntity
from app.reasoning.entity_resolver import EntityResolver
from app.retrieval.rrf import RRFComposer
from app.retrieval.semantic_retriever import SemanticRetriever
from app.utils.logger import logger


class HybridRetriever:
    """Orchestrates multi-modal retrieval across Neo4j graph relationships and Qdrant semantic vectors."""

    def __init__(
        self,
        entity_resolver: EntityResolver | None = None,
        graph_query_manager: GraphQueryManager | None = None,
        semantic_retriever: SemanticRetriever | None = None,
        rrf_composer: RRFComposer | None = None,
    ):
        self.entity_resolver = entity_resolver or EntityResolver()
        self.graph_query_manager = graph_query_manager or GraphQueryManager()
        self.semantic_retriever = semantic_retriever or SemanticRetriever()
        self.rrf_composer = rrf_composer or RRFComposer()

    def retrieve(
        self,
        query: str,
        analysis: QueryAnalysisResult | None = None,
        graph_top_k: int = 10,
        semantic_top_k: int = 10,
        final_top_k: int = 10,
        repository_id: str | None = None,
    ) -> tuple[list[NormalizedSearchResult], list[ResolvedEntity]]:
        """Run parallel retrieval pipelines (Graph + Vector) and merge with RRF fusion."""
        logger.info(f"Hybrid retrieval starting for query: '{query}'")

        # 1. Entity Resolution
        candidate_terms = analysis.candidate_symbols if analysis else []
        resolved_entities = self.entity_resolver.resolve(query, candidate_terms)
        logger.info(f"Resolved {len(resolved_entities)} entities for graph retrieval.")

        # 2. Graph Retrieval
        graph_results = self._retrieve_graph_context(
            query=query,
            analysis=analysis,
            resolved_entities=resolved_entities,
            limit=graph_top_k,
        )

        # 3. Semantic Vector Retrieval
        semantic_results = self.semantic_retriever.retrieve(
            query=query,
            limit=semantic_top_k,
            repository_id=repository_id,
        )

        # 4. RRF Fusion
        fused_results = self.rrf_composer.fuse(
            graph_results=graph_results,
            semantic_results=semantic_results,
            top_k=final_top_k,
        )

        logger.info(
            f"Hybrid retrieval finished: {len(graph_results)} graph items, "
            f"{len(semantic_results)} semantic items -> {len(fused_results)} fused items."
        )

        return fused_results, resolved_entities

    def _retrieve_graph_context(
        self,
        query: str,
        analysis: QueryAnalysisResult | None,
        resolved_entities: list[ResolvedEntity],
        limit: int = 10,
    ) -> list[NormalizedSearchResult]:
        """Query Neo4j graph based on resolved entities and query intent."""
        graph_results: list[NormalizedSearchResult] = []
        seen_keys: set[str] = set()

        if not resolved_entities:
            return graph_results

        intent = analysis.intent if analysis else "general_code_question"
        max_hops = analysis.requested_hops if analysis else 2

        for entity in resolved_entities[:3]:
            records: list[dict[str, Any]] = []

            if intent in ("callers", "general_code_question"):
                records.extend(self.graph_query_manager.find_callers(entity.qualified_name))
            if intent in ("callees", "general_code_question"):
                records.extend(self.graph_query_manager.find_callees(entity.qualified_name))
            if intent in ("dependency", "architecture"):
                records.extend(self.graph_query_manager.find_dependencies(entity.qualified_name))
            if intent == "impact":
                records.extend(self.graph_query_manager.find_impact_subgraph(entity.qualified_name, max_depth=max_hops))

            # Direct symbol details if few records found
            records.extend(self.graph_query_manager.find_symbol(entity.qualified_name))

            for rec in records:
                # Normalize graph records into NormalizedSearchResult
                name = (
                    rec.get("caller_name")
                    or rec.get("callee_name")
                    or rec.get("target_name")
                    or rec.get("source_name")
                    or rec.get("name")
                    or entity.name
                )
                qn = (
                    rec.get("caller_qn")
                    or rec.get("callee_qn")
                    or rec.get("target_qn")
                    or rec.get("source_qn")
                    or rec.get("qualified_name")
                    or entity.qualified_name
                )
                fpath = rec.get("file_path") or entity.file_path
                start_l = int(rec.get("start_line") or entity.start_line or 1)
                end_l = int(rec.get("end_line") or entity.end_line or start_l)
                doc = rec.get("docstring") or ""
                sym_type = entity.symbol_type

                rel_desc = rec.get("relationship") or ""
                content_str = f"Graph Symbol: {qn} ({sym_type})\nFile: {fpath}:{start_l}-{end_l}"
                if rel_desc:
                    content_str += f"\nRelationship: {rel_desc}"
                if doc:
                    content_str += f"\nDocstring: {doc}"

                key = f"{fpath}:{qn}:{start_l}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    graph_results.append(
                        NormalizedSearchResult(
                            id=f"graph_{key}",
                            source="graph",
                            repository_id="default",
                            file_path=fpath,
                            symbol_name=name,
                            qualified_name=qn,
                            symbol_type=sym_type,
                            start_line=start_l,
                            end_line=end_l,
                            content=content_str,
                            score=1.0,
                            rrf_score=0.0,
                        )
                    )

                if len(graph_results) >= limit:
                    break
            if len(graph_results) >= limit:
                break

        return graph_results
