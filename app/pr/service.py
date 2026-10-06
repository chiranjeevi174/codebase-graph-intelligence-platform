"""PR Analysis Service orchestrating structural diff, impact analysis, Qdrant evidence, and PR comment posting."""

import hashlib

from app.analysis.impact_service import CodeImpactAnalysisService
from app.diff.diff_analyzer import StructuralDiffAnalyzer
from app.diff.diff_models import DiffRequest
from app.graph.graph_queries import GraphQueryManager
from app.integrations.factory import PRProviderFactory
from app.models.entities import ImpactAnalysisRequest
from app.pr.comment_formatter import PRCommentFormatter
from app.pr.models import (
    PRAnalysisEvidence,
    PRAnalysisRequest,
    PRAnalysisResult,
    PRAnalysisSummary,
)
from app.reasoning.answer_validator import AnswerValidator
from app.retrieval.semantic_retriever import SemanticRetriever
from app.utils.logger import logger


class PRAnalysisService:
    """Orchestrates end-to-end pull request analysis across structural diff, impact, and evidence generation."""

    def __init__(
        self,
        diff_analyzer: StructuralDiffAnalyzer | None = None,
        impact_service: CodeImpactAnalysisService | None = None,
        graph_query_manager: GraphQueryManager | None = None,
        semantic_retriever: SemanticRetriever | None = None,
        answer_validator: AnswerValidator | None = None,
    ):
        self.diff_analyzer = diff_analyzer or StructuralDiffAnalyzer()
        self.impact_service = impact_service or CodeImpactAnalysisService()
        self.graph_query_manager = graph_query_manager or GraphQueryManager()
        self.semantic_retriever = semantic_retriever or SemanticRetriever()
        self.answer_validator = answer_validator or AnswerValidator()

    def analyze_pr(self, request: PRAnalysisRequest) -> PRAnalysisResult:
        """Run complete evidence-backed PR analysis pipeline."""
        repo = request.repository
        pr_num = request.pr_number
        base_ref = request.base_ref
        target_ref = request.target_ref

        # Generate deterministic run ID
        run_key = f"{request.provider}:{repo}:{pr_num}:{base_ref}:{target_ref}"
        run_id = f"pr_run_{hashlib.md5(run_key.encode('utf-8')).hexdigest()[:12]}"

        logger.info(
            f"[PRAnalysisService:pr_analysis_started] Starting PR analysis for {repo} #{pr_num} (Run ID: {run_id})"
        )

        # Step 1: Execute Structural Git Diff
        diff_req = DiffRequest(
            repository_id=request.repository.split("/")[-1],
            repo_path=request.repo_path,
            base_ref=base_ref,
            target_ref=target_ref,
            max_hops=request.max_hops,
            max_nodes=request.max_nodes,
            max_relationships=request.max_relationships,
        )

        try:
            diff_res = self.diff_analyzer.analyze_diff(diff_req)
        except Exception as e:  # noqa: BLE001 — Fallback gracefully if diff analysis fails
            logger.warning(f"[PRAnalysisService] Structural diff error for {repo}: {e}")
            diff_res = None

        struct_diff = diff_res.structural_diff if diff_res else None

        changed_files = [fc.file_path for fc in (struct_diff.files_changed if struct_diff else [])]
        changed_symbols = [
            {
                "symbol_name": sc.symbol_name,
                "qualified_name": sc.qualified_name,
                "file_path": sc.file_path,
                "change_type": sc.change_type.value if hasattr(sc.change_type, "value") else str(sc.change_type),
                "symbol_type": sc.symbol_type,
            }
            for sc in (struct_diff.symbols_changed if struct_diff else [])
        ]

        sig_changes = []
        for sc in struct_diff.symbols_changed if struct_diff else []:
            if sc.signature_change and sc.signature_change.signature_changed:
                sig_changes.append(
                    {
                        "symbol_name": sc.symbol_name,
                        "qualified_name": sc.qualified_name,
                        "old_signature": sc.signature_change.old_signature,
                        "new_signature": sc.signature_change.new_signature,
                        "added_parameters": sc.signature_change.parameter_added,
                        "removed_parameters": sc.signature_change.parameter_removed,
                    }
                )

        api_changes = [
            {
                "endpoint_id": ac.endpoint_id,
                "http_method": ac.http_method,
                "path": ac.path,
                "change_type": ac.change_type.value if hasattr(ac.change_type, "value") else str(ac.change_type),
            }
            for ac in (struct_diff.api_changes if struct_diff else [])
        ]

        logger.info(
            f"[PRAnalysisService:pr_diff_completed] Found {len(changed_files)} changed files and {len(changed_symbols)} changed symbols."
        )

        # Step 2: Impact Analysis around changed symbols
        affected_files_set = set(changed_files)
        affected_components_set = set()
        cross_language_impacts = []
        evidence_items = []

        for sc in struct_diff.symbols_changed if struct_diff else []:
            sym_name = sc.qualified_name or sc.symbol_name
            try:
                imp_res = self.impact_service.analyze_impact(
                    ImpactAnalysisRequest(
                        symbol=sym_name,
                        repository_id=request.repository.split("/")[-1],
                        max_hops=request.max_hops,
                        max_nodes=request.max_nodes,
                        max_relationships=request.max_relationships,
                    )
                )
                for node in imp_res.direct_dependents + imp_res.transitive_dependents:
                    affected_components_set.add(f"{node.qualified_name} ({node.file_path}:{node.start_line or 1})")
                    if node.file_path and node.file_path != "unknown":
                        affected_files_set.add(node.file_path)

                # Cross-language API check
                flows = self.graph_query_manager.find_api_flow(sym_name, max_hops=request.max_hops)
                for fl in flows:
                    cross_language_impacts.append(
                        {
                            "symbol": sym_name,
                            "description": f"Cross-language flow: {' -> '.join(fl.get('path_relationships', []))}",
                        }
                    )

                # Collect static evidence
                evidence_items.append(
                    PRAnalysisEvidence(
                        symbol=sym_name,
                        file_path=sc.file_path,
                        line_range=f"{sc.start_line}-{sc.end_line}",
                        evidence_type="static_graph",
                        description=f"Symbol modified: {sc.symbol_name} ({sc.symbol_type})",
                    )
                )
            except Exception as ie:  # noqa: BLE001 — Impact analysis fallback per symbol
                logger.debug(f"Impact check warning for {sym_name}: {ie}")

        logger.info(
            f"[PRAnalysisService:pr_impact_completed] Identified {len(affected_components_set)} affected components across {len(affected_files_set)} files."
        )

        # Step 3: Supporting Qdrant Vector Context Retrieval
        if changed_symbols:
            try:
                vec_chunks = self.semantic_retriever.retrieve(
                    query=changed_symbols[0].get("qualified_name") or changed_symbols[0].get("symbol_name") or "",
                    limit=3,
                    repository_id=request.repository.split("/")[-1],
                )
                for chunk in vec_chunks:
                    evidence_items.append(
                        PRAnalysisEvidence(
                            symbol=chunk.symbol_name or "VectorChunk",
                            file_path=chunk.file_path,
                            line_range=f"{chunk.start_line}-{chunk.end_line}",
                            evidence_type="vector_chunk",
                            description="Supporting semantic context retrieved from Qdrant",
                        )
                    )
            except Exception as qe:  # noqa: BLE001 — Vector store optional context retrieval boundary
                logger.debug(f"Qdrant evidence warning: {qe}")

        # Step 4: Summary Aggregation
        summary = PRAnalysisSummary(
            changed_files_count=len(changed_files),
            changed_symbols_count=len(changed_symbols),
            signature_changes_count=len(sig_changes),
            api_changes_count=len(api_changes),
            affected_files_count=len(affected_files_set),
            cross_language_impacts_count=len(cross_language_impacts),
        )

        explanation = diff_res.explanation if diff_res else "Static analysis completed."

        # Step 5: Answer Validation
        is_valid = True
        try:
            is_valid, _ = self.answer_validator.validate(
                answer=explanation or "",
                fused_results=[],
                resolved_entities=[],
            )
        except Exception as ve:  # noqa: BLE001 # Non-blocking answer validation resilience boundary
            logger.warning(f"Answer validation warning during PR analysis: {ve}")

        result = PRAnalysisResult(
            analysis_run_id=run_id,
            provider=request.provider,
            repository=request.repository,
            pr_number=request.pr_number,
            base_sha=struct_diff.base_commit_hash if struct_diff else base_ref,
            head_sha=struct_diff.target_commit_hash if struct_diff else target_ref,
            summary=summary,
            changed_files=changed_files,
            changed_symbols=changed_symbols,
            signature_changes=sig_changes,
            relationship_changes=[],
            api_changes=api_changes,
            contract_changes=[],
            affected_components=sorted(affected_components_set),
            affected_files=sorted(affected_files_set),
            cross_language_impacts=cross_language_impacts,
            evidence=evidence_items,
            explanation=explanation or "Static PR analysis completed.",
            validation_status=is_valid,
            dry_run=request.dry_run,
        )

        # Step 6: Format & Optional Comment Posting
        comment_body = PRCommentFormatter.format_comment(result)
        if not request.dry_run:
            try:
                provider = PRProviderFactory.get_provider(request.provider)
                existing_comment_id = provider.find_existing_comment_id(request.repository, request.pr_number)
                if existing_comment_id:
                    comment_obj = provider.update_comment(request.repository, existing_comment_id, comment_body)
                    logger.info(
                        f"[PRAnalysisService:pr_comment_updated] Updated existing PR comment ({existing_comment_id}) on {request.repository} #{request.pr_number}"
                    )
                else:
                    comment_obj = provider.post_comment(request.repository, request.pr_number, comment_body)
                    logger.info(
                        f"[PRAnalysisService:pr_comment_posted] Posted new PR comment on {request.repository} #{request.pr_number}"
                    )
                result.comment = comment_obj
            except Exception as pe:  # noqa: BLE001 — External SCM provider comment posting boundary
                logger.warning(f"Failed posting PR comment: {pe}")

        logger.info(f"[PRAnalysisService:pr_analysis_completed] Completed PR analysis run {run_id}.")
        return result
