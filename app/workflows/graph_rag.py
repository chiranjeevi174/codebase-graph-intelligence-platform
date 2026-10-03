"""LangGraph Graph RAG workflow state machine and orchestration pipeline for Phase 2.2."""

from typing import Any
from typing_extensions import TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.graph_queries import GraphQueryManager
from app.graph.subgraph_builder import FocusedSubgraph, SubgraphBuilder
from app.llm.factory import get_llm
from app.models.entities import (
    GraphPath,
    GraphRAGResponse,
    NormalizedSearchResult,
    QueryAnalysisResult,
    ResolvedEntity,
)
from app.reasoning.answer_validator import AnswerValidator
from app.reasoning.entity_resolver import EntityResolver
from app.reasoning.query_analyzer import QueryAnalyzer
from app.retrieval.context_fusion import ContextFusion
from app.retrieval.rrf import RRFComposer
from app.retrieval.semantic_retriever import SemanticRetriever
from app.utils.logger import logger


class GraphRAGState(TypedDict):
    """Typed workflow state dictionary passed through LangGraph nodes."""

    question: str
    repository_id: str | None
    graph_top_k: int
    semantic_top_k: int
    final_top_k: int
    max_hops: int
    
    query_analysis: QueryAnalysisResult | None
    resolved_entities: list[ResolvedEntity]
    graph_results: list[NormalizedSearchResult]
    semantic_results: list[NormalizedSearchResult]
    fused_results: list[NormalizedSearchResult]
    subgraph: FocusedSubgraph | None
    graph_paths: list[GraphPath]
    fused_context: str | None
    final_answer: str | None
    validation_status: bool
    validation_errors: list[str]
    sources: list[str]


def query_analysis_node(state: GraphRAGState) -> dict[str, Any]:
    """Node 1: Analyze natural language query for intent, candidate terms, and hops."""
    analyzer = QueryAnalyzer()
    analysis = analyzer.analyze(
        query=state["question"],
        repository_id=state.get("repository_id"),
    )
    logger.info(f"[LangGraph Node: query_analysis] Query intent='{analysis.intent}' candidate_symbols={analysis.candidate_symbols}")
    return {"query_analysis": analysis}


def entity_resolution_node(state: GraphRAGState) -> dict[str, Any]:
    """Node 2: Resolve candidate terms against Neo4j to exact or fuzzy graph entities."""
    resolver = EntityResolver()
    analysis = state.get("query_analysis")
    candidate_terms = analysis.candidate_symbols if analysis else []
    resolved = resolver.resolve(query=state["question"], candidate_terms=candidate_terms)
    logger.info(f"[LangGraph Node: entity_resolution] Resolved {len(resolved)} entities.")
    return {"resolved_entities": resolved}


def graph_retrieval_node(state: GraphRAGState) -> dict[str, Any]:
    """Node 3: Retrieve structural relationships from Neo4j for resolved entities."""
    qm = GraphQueryManager()
    resolved = state.get("resolved_entities", [])
    analysis = state.get("query_analysis")
    intent = analysis.intent if analysis else "general_code_question"
    limit = state.get("graph_top_k", 10)

    graph_results: list[NormalizedSearchResult] = []
    seen: set[str] = set()

    for entity in resolved[:3]:
        records: list[dict[str, Any]] = []

        if intent in ("api_flow", "endpoint", "api_client", "api_contract", "cross_language"):
            records.extend(qm.find_api_flow(entity.qualified_name, max_hops=state.get("max_hops", 3)))
            records.extend(qm.find_api_flow(entity.name, max_hops=state.get("max_hops", 3)))
        if intent in ("callers", "general_code_question"):
            records.extend(qm.find_callers(entity.qualified_name))
        if intent in ("callees", "general_code_question"):
            records.extend(qm.find_callees(entity.qualified_name))
        if intent in ("dependency", "architecture"):
            records.extend(qm.find_dependencies(entity.qualified_name))
        if intent == "impact":
            records.extend(qm.find_impact_subgraph(entity.qualified_name, max_depth=state.get("max_hops", 2)))
        if intent == "diff":
            try:
                from app.diff.diff_analyzer import StructuralDiffAnalyzer
                from app.diff.diff_models import DiffRequest
                diff_res = StructuralDiffAnalyzer().analyze_diff(
                    DiffRequest(
                        repository_id=state.get("repository_id") or "default",
                        base_ref="HEAD~1",
                        target_ref="HEAD",
                        max_hops=state.get("max_hops", 3),
                    )
                )
                diff_summary = f"Structural Diff (HEAD~1 -> HEAD): Risk={diff_res.classification}. Files Changed: {len(diff_res.affected_files)}. Explanation: {diff_res.explanation or ''}"
                graph_results.append(
                    NormalizedSearchResult(
                        id="graph_diff_summary",
                        source="graph",
                        repository_id=state.get("repository_id") or "default",
                        file_path=diff_res.affected_files[0] if diff_res.affected_files else "repo_diff",
                        symbol_name="GitDiff",
                        qualified_name="StructuralGitDiff",
                        symbol_type="STRUCTURAL_DIFF",
                        start_line=1,
                        end_line=1,
                        content=diff_summary,
                        score=1.0,
                        rrf_score=0.0,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed extracting diff in Graph RAG: {e}")

        records.extend(qm.find_symbol(entity.qualified_name))

        for rec in records:
            if "path_nodes" in rec:
                p_nodes = rec.get("path_nodes", [])
                p_rels = rec.get("path_relationships", [])
                path_str = " -> ".join([f"{n.get('name')} ({n.get('file_path')}:{n.get('start_line', 1)})" for n in p_nodes if isinstance(n, dict)])
                first_node = p_nodes[0] if p_nodes and isinstance(p_nodes[0], dict) else {}
                fpath = first_node.get("file_path") or entity.file_path
                start_l = int(first_node.get("start_line") or 1)
                end_l = int(first_node.get("end_line") or start_l)
                content_str = f"API Flow Path: {path_str}\nRelationships: {' -> '.join(p_rels)}"
                key = f"api_flow_{fpath}:{start_l}:{path_str[:50]}"
                if key not in seen:
                    seen.add(key)
                    graph_results.append(
                        NormalizedSearchResult(
                            id=f"graph_{key}",
                            source="graph",
                            repository_id=state.get("repository_id") or "default",
                            file_path=fpath,
                            symbol_name=entity.name,
                            qualified_name=entity.qualified_name,
                            symbol_type="API_FLOW",
                            start_line=start_l,
                            end_line=end_l,
                            content=content_str,
                            score=1.0,
                            rrf_score=0.0,
                        )
                    )
            else:
                name = rec.get("caller_name") or rec.get("callee_name") or rec.get("target_name") or rec.get("source_name") or rec.get("name") or entity.name
                qn = rec.get("caller_qn") or rec.get("callee_qn") or rec.get("target_qn") or rec.get("source_qn") or rec.get("qualified_name") or entity.qualified_name
                fpath = rec.get("file_path") or entity.file_path
                start_l = int(rec.get("start_line") or entity.start_line or 1)
                end_l = int(rec.get("end_line") or entity.end_line or start_l)
                doc = rec.get("docstring") or ""
                sym_type = entity.symbol_type

                rel_desc = rec.get("relationship") or ""
                content_str = f"Symbol: {qn} ({sym_type})\nFile: {fpath}:{start_l}-{end_l}"
                if rel_desc:
                    content_str += f"\nRelationship: {rel_desc}"
                if doc:
                    content_str += f"\nDocstring: {doc}"

                key = f"{fpath}:{qn}:{start_l}"
                if key not in seen:
                    seen.add(key)
                    graph_results.append(
                        NormalizedSearchResult(
                            id=f"graph_{key}",
                            source="graph",
                            repository_id=state.get("repository_id") or "default",
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

    logger.info(f"[LangGraph Node: graph_retrieval] Retrieved {len(graph_results)} graph results.")
    return {"graph_results": graph_results}


def semantic_retrieval_node(state: GraphRAGState) -> dict[str, Any]:
    """Node 4: Perform semantic vector search in Qdrant."""
    retriever = SemanticRetriever()
    semantic_results = retriever.retrieve(
        query=state["question"],
        limit=state.get("semantic_top_k", 10),
        repository_id=state.get("repository_id"),
    )
    logger.info(f"[LangGraph Node: semantic_retrieval] Retrieved {len(semantic_results)} semantic vector matches.")
    return {"semantic_results": semantic_results}


def retrieval_fusion_node(state: GraphRAGState) -> dict[str, Any]:
    """Node 5: Fuse graph and semantic retrieval using RRF."""
    composer = RRFComposer(k=60)
    fused = composer.fuse(
        graph_results=state.get("graph_results", []),
        semantic_results=state.get("semantic_results", []),
        top_k=state.get("final_top_k", 10),
    )
    logger.info(f"[LangGraph Node: retrieval_fusion] Produced {len(fused)} fused RRF results.")
    return {"fused_results": fused}


def subgraph_construction_node(state: GraphRAGState) -> dict[str, Any]:
    """Node 6: Extract focused multi-hop subgraph context and paths around seed entities."""
    builder = SubgraphBuilder()
    resolved = state.get("resolved_entities", [])
    subgraph = None
    paths: list[GraphPath] = []

    if resolved:
        seed = resolved[0].qualified_name
        max_hops = state.get("max_hops", 2)
        subgraph = builder.build_subgraph(symbol_identifier=seed, max_hops=max_hops)
        paths = subgraph.paths

    logger.info(f"[LangGraph Node: subgraph_construction] Built subgraph with {len(paths)} graph paths.")
    return {"subgraph": subgraph, "graph_paths": paths}


def context_fusion_node(state: GraphRAGState) -> dict[str, Any]:
    """Node 7: Synthesize graph paths, subgraphs, code snippets, and metadata into prompt context."""
    fusion = ContextFusion()
    fused_text = fusion.fuse_context(
        query=state["question"],
        fused_results=state.get("fused_results", []),
        resolved_entities=state.get("resolved_entities", []),
        subgraph=state.get("subgraph"),
        graph_paths=state.get("graph_paths"),
    )

    sources = list(
        {res.file_path for res in state.get("fused_results", []) if res.file_path}
    )
    logger.info(f"[LangGraph Node: context_fusion] Context compiled ({len(fused_text)} chars). Sources: {len(sources)}")
    return {"fused_context": fused_text, "sources": sources}


def answer_generation_node(state: GraphRAGState) -> dict[str, Any]:
    """Node 8: Generate grounded answer using LLM adhering to evidence grounding constraints."""
    llm = get_llm()
    system_prompt = (
        "You are an expert Codebase Graph Intelligence AI assistant. "
        "Strictly adhere to the following rules:\n"
        "1. Reason ONLY from the supplied codebase evidence and context.\n"
        "2. Do NOT invent code relationships or file paths.\n"
        "3. Explicitly cite source file paths and line ranges in your response (e.g., `src/api/orders.py:20-45`).\n"
        "4. Distinguish observed static relationships from inferred explanations.\n"
        "5. If evidence is incomplete, explicitly acknowledge the uncertainty."
    )

    prompt = f"""User Question:
{state['question']}

Retrieved Codebase Evidence & Graph Context:
{state.get('fused_context', '')}

Provide a comprehensive, accurate, and grounded answer to the question using the context above."""

    try:
        answer = llm.generate(prompt=prompt, system_prompt=system_prompt, temperature=0.2)
    except Exception as e:
        logger.error(f"Error during LLM answer generation: {e}")
        answer = f"Error generating grounded answer: {e}"

    logger.info(f"[LangGraph Node: answer_generation] Answer generated via LLM provider '{llm.provider_name}'.")
    return {"final_answer": answer}


def validation_node(state: GraphRAGState) -> dict[str, Any]:
    """Node 9: Validate generated answer for ungrounded citations and claims."""
    validator = AnswerValidator()
    is_valid, errors = validator.validate(
        answer=state.get("final_answer") or "",
        fused_results=state.get("fused_results", []),
        resolved_entities=state.get("resolved_entities", []),
        graph_results=state.get("graph_results", []),
        graph_paths=state.get("graph_paths", []),
        subgraph=state.get("subgraph"),
    )
    logger.info(f"[LangGraph Node: validation] Groundedness validation status: {is_valid} (errors: {len(errors)})")
    return {"validation_status": is_valid, "validation_errors": errors}


def build_graph_rag_workflow() -> CompiledStateGraph:
    """Construct and compile the Phase 2.2 Graph RAG workflow using LangGraph."""
    workflow = StateGraph(GraphRAGState)

    workflow.add_node("query_analysis", query_analysis_node)
    workflow.add_node("entity_resolution", entity_resolution_node)
    workflow.add_node("graph_retrieval", graph_retrieval_node)
    workflow.add_node("semantic_retrieval", semantic_retrieval_node)
    workflow.add_node("retrieval_fusion", retrieval_fusion_node)
    workflow.add_node("subgraph_construction", subgraph_construction_node)
    workflow.add_node("context_fusion", context_fusion_node)
    workflow.add_node("answer_generation", answer_generation_node)
    workflow.add_node("validation", validation_node)

    workflow.set_entry_point("query_analysis")
    workflow.add_edge("query_analysis", "entity_resolution")
    workflow.add_edge("entity_resolution", "graph_retrieval")
    workflow.add_edge("graph_retrieval", "semantic_retrieval")
    workflow.add_edge("semantic_retrieval", "retrieval_fusion")
    workflow.add_edge("retrieval_fusion", "subgraph_construction")
    workflow.add_edge("subgraph_construction", "context_fusion")
    workflow.add_edge("context_fusion", "answer_generation")
    workflow.add_edge("answer_generation", "validation")
    workflow.add_edge("validation", END)

    return workflow.compile()


class GraphRAGPipeline:
    """High-level Graph RAG intelligence pipeline runner."""

    def __init__(self):
        self.app = build_graph_rag_workflow()

    def run(
        self,
        question: str,
        repository_id: str | None = None,
        graph_top_k: int = 10,
        semantic_top_k: int = 10,
        final_top_k: int = 10,
        max_hops: int = 2,
        debug: bool = False,
    ) -> GraphRAGResponse:
        """Execute the full Graph RAG pipeline for a given user question."""
        initial_state: GraphRAGState = {
            "question": question,
            "repository_id": repository_id,
            "graph_top_k": graph_top_k,
            "semantic_top_k": semantic_top_k,
            "final_top_k": final_top_k,
            "max_hops": max_hops,
            "query_analysis": None,
            "resolved_entities": [],
            "graph_results": [],
            "semantic_results": [],
            "fused_results": [],
            "subgraph": None,
            "graph_paths": [],
            "fused_context": None,
            "final_answer": None,
            "validation_status": True,
            "validation_errors": [],
            "sources": [],
        }

        final_state = self.app.invoke(initial_state)

        analysis = final_state.get("query_analysis")
        intent_str = analysis.intent if analysis else "general_code_question"
        fused_res = final_state.get("fused_results", [])
        graph_paths = [p.model_dump() for p in final_state.get("graph_paths", [])]

        debug_data = None
        if debug:
            debug_data = {
                "query_analysis": analysis.model_dump() if analysis else None,
                "resolved_entities": [e.model_dump() for e in final_state.get("resolved_entities", [])],
                "graph_results_count": len(final_state.get("graph_results", [])),
                "semantic_results_count": len(final_state.get("semantic_results", [])),
                "fused_results": [r.model_dump() for r in fused_res],
                "subgraph_stats": {
                    "nodes": len(final_state["subgraph"].nodes) if final_state.get("subgraph") else 0,
                    "edges": len(final_state["subgraph"].edges) if final_state.get("subgraph") else 0,
                },
                "validation_errors": final_state.get("validation_errors", []),
            }

        return GraphRAGResponse(
            answer=final_state.get("final_answer") or "No answer generated.",
            repository_id=repository_id,
            query=question,
            intent=intent_str,
            sources=final_state.get("sources", []),
            graph_paths=graph_paths,
            retrieved_chunks=[r.model_dump() for r in fused_res],
            retrieval_summary=f"Fused {len(fused_res)} items across graph and semantic search.",
            confidence=0.9 if final_state.get("validation_status") else 0.5,
            validation_status=final_state.get("validation_status", True),
            debug_info=debug_data,
        )
