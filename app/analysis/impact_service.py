"""Code Impact Analysis Engine service layer."""


from app.graph.graph_queries import GraphQueryManager
from app.llm.factory import get_llm
from app.models.entities import (
    ImpactAnalysisRequest,
    ImpactAnalysisResult,
    ImpactNode,
    ImpactPath,
    ImpactSummary,
    NormalizedSearchResult,
    ResolvedEntity,
)
from app.reasoning.entity_resolver import EntityResolver
from app.retrieval.semantic_retriever import SemanticRetriever
from app.utils.logger import logger


class CodeImpactAnalysisService:
    """Analyzes static structural impact and dependency propagation of code symbol modifications."""

    def __init__(
        self,
        entity_resolver: EntityResolver | None = None,
        graph_query_manager: GraphQueryManager | None = None,
        semantic_retriever: SemanticRetriever | None = None,
    ):
        self.entity_resolver = entity_resolver or EntityResolver()
        self.graph_query_manager = graph_query_manager or GraphQueryManager()
        self.semantic_retriever = semantic_retriever or SemanticRetriever()

    def analyze_impact(self, request: ImpactAnalysisRequest) -> ImpactAnalysisResult:
        """Perform static impact analysis around a target code symbol."""
        logger.info(f"[ImpactAnalysisService] Starting impact analysis for symbol: '{request.symbol}' (max_hops={request.max_hops})")

        # 1. Target Symbol Resolution
        resolved_list = self.entity_resolver.resolve(
            query=request.symbol,
            candidate_terms=[request.symbol],
            repository_id=request.repository_id,
        )

        if resolved_list:
            target_entity = resolved_list[0]
        else:
            # Fallback placeholder entity if not in graph
            target_entity = ResolvedEntity(
                symbol_id=f"target_{request.symbol}",
                name=request.symbol.split(".")[-1],
                qualified_name=request.symbol,
                symbol_type="Function",
                file_path="unknown",
                match_type="unresolved",
                confidence=0.0,
            )

        target_qn = target_entity.qualified_name

        # 2. Transitive Upstream Dependents (What depends on target?)
        raw_dependents = self.graph_query_manager.find_transitive_dependents(
            symbol_name_or_qn=target_qn,
            max_hops=request.max_hops,
            limit=request.max_relationships,
        )

        # 3. Transitive Downstream Dependencies (What target depends on?)
        raw_dependencies = self.graph_query_manager.find_transitive_dependencies(
            symbol_name_or_qn=target_qn,
            max_hops=request.max_hops,
            limit=request.max_relationships,
        )

        # 4. Process Direct vs Transitive Impact
        direct_dependents: list[ImpactNode] = []
        transitive_dependents: list[ImpactNode] = []
        direct_dependencies: list[ImpactNode] = []
        transitive_dependencies: list[ImpactNode] = []

        impact_paths: list[ImpactPath] = []
        affected_files_set: set[str] = set()
        affected_symbols_set: set[str] = set()

        if target_entity.file_path and target_entity.file_path != "unknown":
            affected_files_set.add(target_entity.file_path)

        truncated = False
        if len(raw_dependents) >= request.max_relationships or len(raw_dependencies) >= request.max_relationships:
            truncated = True

        # Process Upstream Dependents
        for rec in raw_dependents:
            labels = rec.get("labels", ["Symbol"])
            sym_type = labels[0] if isinstance(labels, list) and labels else "Symbol"
            raw_name = rec.get("name") or rec.get("qualified_name") or "Unknown"
            raw_qn = rec.get("qualified_name") or rec.get("name") or raw_name
            name = str(raw_name)
            qn = str(raw_qn)
            fpath = str(rec.get("file_path") or "unknown")
            hop = int(rec.get("hop_count", 1))
            rel_types = rec.get("rel_types", ["DEPENDS_ON"])
            rel_type = rel_types[0] if rel_types else "DEPENDS_ON"

            if fpath != "unknown":
                affected_files_set.add(fpath)
            affected_symbols_set.add(qn)

            node = ImpactNode(
                symbol_id=str(rec.get("symbol_id") or qn),
                name=name,
                qualified_name=qn,
                symbol_type=sym_type,
                file_path=fpath,
                start_line=rec.get("start_line"),
                end_line=rec.get("end_line"),
                relationship_type=rel_type,
                hop_count=hop,
                impact_category="direct_dependent" if hop == 1 else "transitive_dependent",
            )

            if hop == 1:
                direct_dependents.append(node)
            else:
                transitive_dependents.append(node)

            # Build ImpactPath
            path_nodes = rec.get("path_nodes") or [qn, target_qn]
            path_files = rec.get("path_files") or [fpath]
            impact_paths.append(
                ImpactPath(
                    source_symbol=str(path_nodes[0]) if path_nodes else qn,
                    target_symbol=target_qn,
                    hop_count=hop,
                    path_sequence=[str(p) for p in path_nodes if p],
                    file_paths=[str(f) for f in path_files if f],
                )
            )

        # Process Downstream Dependencies
        for rec in raw_dependencies:
            labels = rec.get("labels", ["Symbol"])
            sym_type = labels[0] if isinstance(labels, list) and labels else "Symbol"
            raw_name = rec.get("name") or rec.get("qualified_name") or "Unknown"
            raw_qn = rec.get("qualified_name") or rec.get("name") or raw_name
            name = str(raw_name)
            qn = str(raw_qn)
            fpath = str(rec.get("file_path") or "unknown")
            hop = int(rec.get("hop_count", 1))
            rel_types = rec.get("rel_types", ["DEPENDS_ON"])
            rel_type = rel_types[0] if rel_types else "DEPENDS_ON"

            if fpath != "unknown":
                affected_files_set.add(fpath)
            affected_symbols_set.add(qn)

            node = ImpactNode(
                symbol_id=str(rec.get("symbol_id") or qn),
                name=name,
                qualified_name=qn,
                symbol_type=sym_type,
                file_path=fpath,
                start_line=rec.get("start_line"),
                end_line=rec.get("end_line"),
                relationship_type=rel_type,
                hop_count=hop,
                impact_category="direct_dependency" if hop == 1 else "transitive_dependency",
            )

            if hop == 1:
                direct_dependencies.append(node)
            else:
                transitive_dependencies.append(node)

        # 5. Aggregate Structural Metrics (ImpactSummary)
        summary = ImpactSummary(
            direct_dependents_count=len(direct_dependents),
            transitive_dependents_count=len(transitive_dependents),
            direct_dependencies_count=len(direct_dependencies),
            transitive_dependencies_count=len(transitive_dependencies),
            affected_files_count=len(affected_files_set),
            affected_symbols_count=len(affected_symbols_set),
            max_hops_used=request.max_hops,
            analysis_truncated=truncated,
        )

        # 6. Retrieve Supplementary Qdrant Vector Context for target and impacted entities
        evidence_snippets: list[NormalizedSearchResult] = self.semantic_retriever.retrieve(
            query=target_qn,
            limit=5,
            repository_id=request.repository_id,
        )

        # 7. Grounded LLM Explanation
        explanation = self._generate_llm_explanation(
            target=target_entity,
            summary=summary,
            direct_dependents=direct_dependents,
            transitive_dependents=transitive_dependents,
            direct_dependencies=direct_dependencies,
            impact_paths=impact_paths,
            evidence=evidence_snippets,
        )

        return ImpactAnalysisResult(
            target=target_entity,
            summary=summary,
            direct_dependencies=direct_dependencies,
            direct_dependents=direct_dependents,
            transitive_dependencies=transitive_dependencies,
            transitive_dependents=transitive_dependents,
            impact_paths=impact_paths[:15],
            affected_files=sorted(list(affected_files_set)),
            evidence_snippets=evidence_snippets,
            explanation=explanation,
            analysis_truncated=truncated,
        )

    def _generate_llm_explanation(
        self,
        target: ResolvedEntity,
        summary: ImpactSummary,
        direct_dependents: list[ImpactNode],
        transitive_dependents: list[ImpactNode],
        direct_dependencies: list[ImpactNode],
        impact_paths: list[ImpactPath],
        evidence: list[NormalizedSearchResult],
    ) -> str:
        """Generate grounded natural-language explanation of static impact using LLM provider abstraction."""
        llm = get_llm()

        system_prompt = (
            "You are an expert AI software architect performing Code Impact Analysis.\n"
            "STRICT GUIDELINES:\n"
            "1. Report ONLY observed static code relationships (CALLS, DEPENDS_ON, IMPORTS, INHERITS).\n"
            "2. Never claim a downstream component will definitely fail or break at runtime. Use precise phrasing: "
            "'Static analysis identifies these downstream dependencies that may require review...'\n"
            "3. Cite exact file paths and line ranges for all mentioned entities.\n"
            "4. Clearly distinguish direct impact (1-hop) from transitive impact (>1 hop).\n"
            "5. State any uncertainty if static analysis cannot fully determine runtime behavior."
        )

        deps_summary = "\n".join(
            [f"- {d.name} ({d.symbol_type}) in `{d.file_path}:{d.start_line or 1}` [{d.relationship_type}]" for d in direct_dependents[:10]]
        ) or "None observed."

        trans_summary = "\n".join(
            [f"- {t.name} ({t.symbol_type}) in `{t.file_path}:{t.start_line or 1}` [{t.hop_count} hops away]" for t in transitive_dependents[:10]]
        ) or "None observed."

        downstream_summary = "\n".join(
            [f"- {d.name} ({d.symbol_type}) in `{d.file_path}:{d.start_line or 1}` [{d.relationship_type}]" for d in direct_dependencies[:10]]
        ) or "None observed."

        paths_summary = "\n".join(
            [f"- {' -> '.join(p.path_sequence)}" for p in impact_paths[:5]]
        ) or "None."

        prompt = f"""Target Symbol Analyzed: `{target.qualified_name}` (File: `{target.file_path}:{target.start_line or 1}-{target.end_line or 1}`)

Structural Measurements:
- Direct Upstream Dependents: {summary.direct_dependents_count}
- Transitive Upstream Dependents: {summary.transitive_dependents_count}
- Direct Downstream Dependencies: {summary.direct_dependencies_count}
- Transitive Downstream Dependencies: {summary.transitive_dependencies_count}
- Total Affected Files: {summary.affected_files_count}
- Traversal Max Depth: {summary.max_hops_used}
- Analysis Truncated: {summary.analysis_truncated}

Direct Upstream Dependents (Who relies on this symbol?):
{deps_summary}

Transitive Upstream Dependents (>1 Hop Away):
{trans_summary}

Direct Downstream Dependencies (What does this symbol rely on?):
{downstream_summary}

Sample Impact Paths:
{paths_summary}

Explain the structural impact of modifying `{target.name}` grounded in these static relationships."""

        try:
            explanation = llm.generate(prompt=prompt, system_prompt=system_prompt, temperature=0.2)
        except Exception as e:
            logger.error(f"Error generating impact explanation via LLM: {e}")
            explanation = (
                f"Static analysis identifies {summary.direct_dependents_count} direct dependents and "
                f"{summary.transitive_dependents_count} transitive dependents across {summary.affected_files_count} files."
            )

        return explanation
