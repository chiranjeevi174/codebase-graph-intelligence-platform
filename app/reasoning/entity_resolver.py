"""Entity Resolver for matching candidate query terms against graph nodes and vector store."""

from app.graph.graph_queries import GraphQueryManager
from app.models.entities import ResolvedEntity
from app.utils.logger import logger


class EntityResolver:
    """Resolves entity candidates against the Neo4j knowledge graph and semantic indexes."""

    def __init__(self, query_manager: GraphQueryManager | None = None):
        self.query_manager = query_manager or GraphQueryManager()

    def resolve(
        self,
        query: str | None = None,
        candidate_terms: list[str] | None = None,
        candidate_files: list[str] | None = None,
        repository_id: str | None = None,
    ) -> list[ResolvedEntity]:
        """Flexible resolution interface accepting query string or candidate terms."""
        terms = candidate_terms or []
        if query and not terms:
            words = query.split()
            terms = [w.strip("?,.()") for w in words if any(c.isupper() or "_" in w for c in w)]
        return self.resolve_entities(
            candidate_symbols=terms,
            candidate_files=candidate_files,
            repository_id=repository_id,
        )

    def resolve_entities(
        self,
        candidate_symbols: list[str],
        candidate_files: list[str] | None = None,
        repository_id: str | None = None,
    ) -> list[ResolvedEntity]:
        """Resolves target symbol strings to actual graph nodes or code symbols.

        Args:
            candidate_symbols: List of candidate symbol names extracted from query.
            candidate_files: List of file path hints.
            repository_id: Optional repository scope.

        Returns:
            List of ResolvedEntity objects.
        """
        resolved_entities: list[ResolvedEntity] = []
        seen_ids = set()

        for term in candidate_symbols:
            try:
                # 1. Exact or Qualified Graph Lookup in Neo4j
                matches = self.query_manager.find_symbol(term)
                if matches:
                    for m in matches:
                        symbol_id = str(m.get("symbol_id") or m.get("name") or term)
                        qn = str(m.get("qualified_name") or m.get("name") or term)
                        if symbol_id not in seen_ids:
                            seen_ids.add(symbol_id)
                            labels = m.get("labels", ["Function"])
                            sym_type = labels[0] if isinstance(labels, list) and labels else "Function"
                            resolved_entities.append(
                                ResolvedEntity(
                                    symbol_id=symbol_id,
                                    name=m.get("name", term),
                                    qualified_name=qn,
                                    symbol_type=sym_type,
                                    file_path=m.get("file_path", ""),
                                    start_line=m.get("start_line"),
                                    end_line=m.get("end_line"),
                                    match_type="exact",
                                    confidence=1.0,
                                )
                            )
                else:
                    # Fallback: substring / qualified name matching
                    fallback_query = """
                    MATCH (s)
                    WHERE toLower(s.name) CONTAINS toLower($term) OR toLower(s.qualified_name) CONTAINS toLower($term)
                    RETURN labels(s) AS labels, s.name AS name, s.qualified_name AS qualified_name,
                           s.file_path AS file_path, s.start_line AS start_line, s.end_line AS end_line
                    LIMIT 3
                    """
                    sub_matches = self.query_manager.client.execute_read(fallback_query, {"term": term})
                    for m in sub_matches:
                        qn = str(m.get("qualified_name") or m.get("name") or term)
                        symbol_id = f"sub_{qn}"
                        if symbol_id not in seen_ids:
                            seen_ids.add(symbol_id)
                            labels = m.get("labels", ["Function"])
                            sym_type = labels[0] if isinstance(labels, list) and labels else "Function"
                            resolved_entities.append(
                                ResolvedEntity(
                                    symbol_id=symbol_id,
                                    name=m.get("name", term),
                                    qualified_name=qn,
                                    symbol_type=sym_type,
                                    file_path=m.get("file_path", ""),
                                    start_line=m.get("start_line"),
                                    end_line=m.get("end_line"),
                                    match_type="fuzzy",
                                    confidence=0.8,
                                )
                            )
            except Exception as e:  # noqa: BLE001 — Safe entity resolution per-term fallback
                logger.warning(f"Error resolving entity '{term}': {e}")

        logger.info(
            f"[EntityResolver] Resolved {len(resolved_entities)} entities from {len(candidate_symbols)} candidates."
        )
        return resolved_entities
