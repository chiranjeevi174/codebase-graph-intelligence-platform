"""Orchestrator for Structural Git Diff and Change Impact Analysis."""

from typing import Any

from app.analysis.impact_service import CodeImpactAnalysisService
from app.diff.api_diff import ApiDiffEngine
from app.diff.diff_models import (
    ApiChange,
    ChangeClassification,
    ChangeImpact,
    ChangeImpactResult,
    ChangeType,
    ContractChange,
    DiffRequest,
    FileChange,
    RelationshipChange,
    StructuralDiff,
    SymbolChange,
)
from app.diff.git_diff_service import GitDiffService
from app.diff.relationship_diff import RelationshipDiffEngine
from app.diff.structural_diff import StructuralDiffExtractor
from app.diff.symbol_diff import SymbolDiffEngine
from app.graph.graph_queries import GraphQueryManager
from app.llm.factory import get_llm
from app.models.entities import ImpactAnalysisRequest
from app.retrieval.semantic_retriever import SemanticRetriever
from app.utils.logger import logger


class StructuralDiffAnalyzer:
    """Orchestrates structural Git diff extraction, symbol diffing, graph impact analysis, and LLM explanation."""

    def __init__(
        self,
        git_service: GitDiffService | None = None,
        impact_service: CodeImpactAnalysisService | None = None,
        graph_query_manager: GraphQueryManager | None = None,
        semantic_retriever: SemanticRetriever | None = None,
    ):
        self.git_service = git_service
        self.impact_service = impact_service or CodeImpactAnalysisService()
        self.graph_query_manager = graph_query_manager or GraphQueryManager()
        self.semantic_retriever = semantic_retriever or SemanticRetriever()
        self.symbol_diff_engine = SymbolDiffEngine()
        self.relationship_diff_engine = RelationshipDiffEngine()
        self.api_diff_engine = ApiDiffEngine()

    def analyze_diff(self, request: DiffRequest) -> ChangeImpactResult:
        """Execute full structural Git diff and change impact analysis."""
        logger.info(f"[StructuralDiffAnalyzer] diff_started for repo_path='{request.repo_path}', base_ref='{request.base_ref}', target_ref='{request.target_ref}'")

        git_svc = self.git_service or GitDiffService(repo_path=request.repo_path)
        
        base_sha = git_svc.resolve_ref(request.base_ref)
        target_sha = git_svc.resolve_ref(request.target_ref)

        # 1. File-level diff
        file_changes = git_svc.get_changed_files(
            base_ref=request.base_ref,
            target_ref=request.target_ref,
            repository_id=request.repository_id,
        )
        logger.info(f"[StructuralDiffAnalyzer] files_changed: {len(file_changes)}")

        # 2. Extract base and target AST/Tree-sitter snapshots
        extractor = StructuralDiffExtractor(git_service=git_svc)
        snapshot_pairs = extractor.extract_file_snapshots(
            file_changes=file_changes,
            base_ref=request.base_ref,
            target_ref=request.target_ref,
            repository_id=request.repository_id,
        )

        # 3. Symbol-level diff
        symbol_changes = self.symbol_diff_engine.diff_symbols(
            snapshot_pairs=snapshot_pairs,
            repository_id=request.repository_id,
        )
        logger.info(f"[StructuralDiffAnalyzer] symbols_changed: {len(symbol_changes)}")

        # 4. Relationship-level diff
        relationship_changes = self.relationship_diff_engine.diff_relationships(
            snapshot_pairs=snapshot_pairs
        )
        logger.info(f"[StructuralDiffAnalyzer] relationships_changed: {len(relationship_changes)}")

        # 5. API-level diff & contract changes
        api_changes, contract_changes, classification = self.api_diff_engine.diff_api_changes(
            snapshot_pairs=snapshot_pairs,
            repository_id=request.repository_id,
            git_service=git_svc,
        )
        logger.info(f"[StructuralDiffAnalyzer] api_changes_detected: {len(api_changes)}")

        # Assemble StructuralDiff model
        struct_diff = StructuralDiff(
            repository_id=request.repository_id,
            base_ref=request.base_ref,
            target_ref=request.target_ref,
            base_commit_hash=base_sha,
            target_commit_hash=target_sha,
            files_changed=file_changes,
            symbols_changed=symbol_changes,
            relationships_changed=relationship_changes,
            api_changes=api_changes,
            contract_changes=contract_changes,
        )

        # 6. Graph Impact Analysis (Per changed symbol / endpoint)
        logger.info("[StructuralDiffAnalyzer] impact_analysis_started")
        impact_list: list[ChangeImpact] = []
        all_affected_files: set[str] = set()
        all_affected_endpoints: set[str] = set()
        all_affected_clients: set[str] = set()
        evidence_list: list[dict[str, Any]] = []

        # Include files changed directly in affected files
        for fc in file_changes:
            if fc.file_path:
                all_affected_files.add(fc.file_path)

        for sym_chg in symbol_changes:
            impact_req = ImpactAnalysisRequest(
                symbol=sym_chg.qualified_name or sym_chg.symbol_name,
                repository_id=request.repository_id,
                max_hops=request.max_hops,
                max_nodes=request.max_nodes,
                max_relationships=request.max_relationships,
            )
            try:
                impact_res = self.impact_service.analyze_impact(impact_req)
                
                direct_deps = [n.qualified_name for n in impact_res.direct_dependents]
                trans_deps = [n.qualified_name for n in impact_res.transitive_dependents]
                direct_calls = [n.qualified_name for n in impact_res.direct_dependencies]
                trans_calls = [n.qualified_name for n in impact_res.transitive_dependencies]

                affected_files = list(impact_res.affected_files)
                all_affected_files.update(affected_files)

                # Check for cross-language API endpoint / client links in Neo4j
                api_flows = self.graph_query_manager.find_api_flow(
                    identifier=sym_chg.qualified_name,
                    max_hops=request.max_hops,
                )
                affected_eps: set[str] = set()
                affected_cls: set[str] = set()
                affected_cnts: set[str] = set()

                for flow in api_flows:
                    nodes = flow.get("path_nodes", [])
                    for node in nodes:
                        if isinstance(node, dict):
                            labels = node.get("labels", [])
                            if "ApiEndpoint" in labels or "endpoint_id" in node:
                                ep_id = node.get("endpoint_id") or node.get("path")
                                if ep_id:
                                    affected_eps.add(ep_id)
                                    all_affected_endpoints.add(ep_id)
                            elif "ApiClientCall" in labels or "call_id" in node:
                                cl_id = node.get("call_id") or node.get("url")
                                if cl_id:
                                    affected_cls.add(cl_id)
                                    all_affected_clients.add(cl_id)
                            elif "ApiContract" in labels or "contract_id" in node:
                                cnt_id = node.get("contract_id") or node.get("path_template")
                                if cnt_id:
                                    affected_cnts.add(cnt_id)

                impact_list.append(
                    ChangeImpact(
                        changed_symbol=sym_chg.qualified_name,
                        change_type=sym_chg.change_type,
                        direct_dependents=direct_deps,
                        transitive_dependents=trans_deps,
                        direct_dependencies=direct_calls,
                        transitive_dependencies=trans_calls,
                        affected_files=affected_files,
                        affected_api_endpoints=list(affected_eps),
                        affected_api_clients=list(affected_cls),
                        affected_contracts=list(affected_cnts),
                    )
                )

                # Evidence collection
                evidence_list.append({
                    "symbol": sym_chg.qualified_name,
                    "symbol_type": sym_chg.symbol_type,
                    "file_path": sym_chg.file_path,
                    "start_line": sym_chg.start_line,
                    "end_line": sym_chg.end_line,
                    "change_type": sym_chg.change_type.value,
                    "dependents_count": len(direct_deps) + len(trans_deps),
                    "signature_changed": bool(sym_chg.signature_change and sym_chg.signature_change.signature_changed),
                })
            except Exception as e:
                logger.warning(f"[StructuralDiffAnalyzer] Impact analysis failed for {sym_chg.qualified_name}: {e}")

        for ac in api_changes:
            if ac.endpoint_removed or ac.path_changed or ac.method_changed:
                if classification == ChangeClassification.STRUCTURAL_CHANGE.value:
                    classification = ChangeClassification.POTENTIALLY_BREAKING.value

        logger.info("[StructuralDiffAnalyzer] impact_analysis_completed")

        # 7. LLM Explanation Synthesis
        explanation = self._generate_explanation(
            struct_diff=struct_diff,
            impacts=impact_list,
            classification=classification,
            affected_files=list(all_affected_files),
        )

        logger.info("[StructuralDiffAnalyzer] diff_completed")

        return ChangeImpactResult(
            repository_id=request.repository_id,
            base_ref=request.base_ref,
            target_ref=request.target_ref,
            structural_diff=struct_diff,
            impact=impact_list,
            affected_files=sorted(list(all_affected_files)),
            affected_api_endpoints=sorted(list(all_affected_endpoints)),
            affected_api_clients=sorted(list(all_affected_clients)),
            classification=classification,
            explanation=explanation,
            evidence=evidence_list,
        )

    def _generate_explanation(
        self,
        struct_diff: StructuralDiff,
        impacts: list[ChangeImpact],
        classification: str,
        affected_files: list[str],
    ) -> str:
        """Generate structured natural language explanation using LLM provider abstraction."""
        prompt = f"""You are a static code graph intelligence assistant. Summarize the structural changes between Git references {struct_diff.base_ref} and {struct_diff.target_ref}.

STRUCTURAL DIFF DATA:
- Files Changed: {len(struct_diff.files_changed)}
- Symbols Changed: {len(struct_diff.symbols_changed)}
- Graph Relationships Changed: {len(struct_diff.relationships_changed)}
- API Endpoint Changes: {len(struct_diff.api_changes)}
- OpenAPI Contract Changes: {len(struct_diff.contract_changes)}
- Overall Risk Classification: {classification}

CHANGED SYMBOLS SUMMARY:
{self._format_symbols_summary(struct_diff.symbols_changed)}

CHANGED API ENDPOINTS SUMMARY:
{self._format_api_summary(struct_diff.api_changes)}

IMPACT ANALYSIS DATA:
{self._format_impact_summary(impacts)}

INSTRUCTIONS:
1. Explain observed structural changes clearly.
2. Distinguish static graph evidence from potential runtime inference.
3. Use strict probabilistic/static language ("Static graph analysis identifies...", "Potentially affected components include...", "Evidence indicates...").
4. Never fabricate file paths or line numbers. Cite actual source references from the diff data.
"""
        try:
            llm = get_llm()
            return llm.generate(prompt)
        except Exception as e:
            logger.warning(f"[StructuralDiffAnalyzer] LLM explanation fallback: {e}")
            return (
                f"Static graph analysis identifies {len(struct_diff.symbols_changed)} changed symbols and "
                f"{len(struct_diff.api_changes)} API changes between {struct_diff.base_ref} and {struct_diff.target_ref}. "
                f"Classification: {classification}. Potentially affected files: {', '.join(affected_files[:10])}."
            )

    def _format_symbols_summary(self, symbols: list[SymbolChange]) -> str:
        lines = []
        for s in symbols[:15]:
            sig_str = f" Signature changed: {s.signature_change.old_signature} -> {s.signature_change.new_signature}" if s.signature_change and s.signature_change.signature_changed else ""
            lines.append(f"- [{s.change_type.value}] {s.symbol_type} {s.qualified_name} in {s.file_path}:{s.start_line}-{s.end_line}{sig_str}")
        return "\n".join(lines) if lines else "No symbol changes detected."

    def _format_api_summary(self, api_changes: list[ApiChange]) -> str:
        lines = []
        for a in api_changes[:10]:
            lines.append(f"- [{a.change_type.value}] Endpoint {a.http_method} {a.path} (old: {a.old_http_method or ''} {a.old_path or ''})")
        return "\n".join(lines) if lines else "No API changes detected."

    def _format_impact_summary(self, impacts: list[ChangeImpact]) -> str:
        lines = []
        for imp in impacts[:10]:
            deps_count = len(imp.direct_dependents) + len(imp.transitive_dependents)
            lines.append(f"- Symbol '{imp.changed_symbol}': {deps_count} dependent symbols, {len(imp.affected_files)} affected files, {len(imp.affected_api_clients)} client references.")
        return "\n".join(lines) if lines else "No graph impact recorded."
