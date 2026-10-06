"""Context Fusion module combining Graph subgraphs, multi-hop paths, and semantic code chunks into prompt context."""

from app.graph.subgraph_builder import FocusedSubgraph
from app.models.entities import GraphPath, NormalizedSearchResult, ResolvedEntity


class ContextFusion:
    """Assembles structured, citation-rich prompt context for downstream LLM reasoning."""

    def fuse_context(
        self,
        query: str,
        fused_results: list[NormalizedSearchResult],
        resolved_entities: list[ResolvedEntity],
        subgraph: FocusedSubgraph | None = None,
        graph_paths: list[GraphPath] | None = None,
    ) -> str:
        """Combine structured graph topology and vector code snippets into a formatted context block."""
        sections: list[str] = []

        # 1. Resolved Symbols Section
        if resolved_entities:
            entities_lines = ["### RESOLVED CODE ENTITIES:"]
            for entity in resolved_entities:
                entities_lines.append(
                    f"- {entity.name} ({entity.symbol_type}) -> `{entity.qualified_name}` "
                    f"in `{entity.file_path}:{entity.start_line or 1}-{entity.end_line or 1}` "
                    f"(Match: {entity.match_type})"
                )
            sections.append("\n".join(entities_lines))

        # 2. Graph Paths Section
        all_paths: list[GraphPath] = []
        if graph_paths:
            all_paths.extend(graph_paths)
        if subgraph and subgraph.paths:
            all_paths.extend(subgraph.paths)

        if all_paths:
            path_lines = ["### MULTI-HOP GRAPH PATHS:"]
            seen_seqs: set[str] = set()
            for path in all_paths[:10]:
                seq_str = " ".join(path.path_sequence)
                if seq_str not in seen_seqs:
                    seen_seqs.add(seq_str)
                    path_lines.append(f"- [{path.hop_count} hops] {seq_str}")
            sections.append("\n".join(path_lines))

        # 3. Subgraph Topology Section
        if subgraph and subgraph.edges:
            subgraph_lines = ["### SUBGRAPH NEIGHBORHOOD TOPOLOGY:"]
            seen_edges: set[str] = set()
            for edge in subgraph.edges[:15]:
                edge_str = f"- `{edge.source_id}` -[{edge.relationship_type}]-> `{edge.target_id}`"
                if edge_str not in seen_edges:
                    seen_edges.add(edge_str)
                    subgraph_lines.append(edge_str)
            sections.append("\n".join(subgraph_lines))

        # 4. Retrieved Code Snippets Section (with file path and line citations)
        if fused_results:
            code_lines = ["### RETRIEVED CODE SNIPPETS & METADATA:"]
            for idx, res in enumerate(fused_results, start=1):
                sym_header = f"Symbol: {res.qualified_name or res.symbol_name or 'N/A'}"
                prov = f"[Source: {res.source.upper()} | RRF Score: {res.rrf_score:.4f}]"
                citation = f"File: {res.file_path}:{res.start_line}-{res.end_line}"

                snippet = (
                    f"--- Snippet #{idx} ({prov}) ---\n{sym_header}\n{citation}\n\n```\n{res.content.strip()}\n```"
                )
                code_lines.append(snippet)
            sections.append("\n".join(code_lines))

        if not sections:
            return "No relevant repository context found for this query."

        return "\n\n".join(sections)
