"""Centralized graph query layer for relationship and dependency retrieval."""

from typing import Any

from app.graph.neo4j_client import Neo4jClient


class GraphQueryManager:
    """Provides high-level graph query abstractions for Graph RAG retrieval."""

    def __init__(self, client: Neo4jClient | None = None):
        self.client = client or Neo4jClient()

    def find_symbol(self, identifier: str) -> list[dict[str, Any]]:
        """Find nodes matching a symbol name, qualified name, or API endpoint/URL path."""
        query = """
        MATCH (s)
        WHERE s.name = $id OR s.qualified_name = $id OR s.symbol_id = $id
           OR (s:ApiEndpoint AND (s.endpoint_id = $id OR s.path = $id))
           OR (s:ApiClientCall AND (s.call_id = $id OR s.url = $id))
           OR (s:ApiContract AND (s.contract_id = $id OR s.path_template = $id))
        RETURN labels(s) AS labels, coalesce(s.symbol_id, s.endpoint_id, s.call_id, s.contract_id) AS symbol_id,
               s.name AS name, s.qualified_name AS qualified_name,
               s.file_path AS file_path, s.start_line AS start_line, s.end_line AS end_line,
               s.docstring AS docstring
        """
        return self.client.execute_read(query, {"id": identifier})

    def find_symbols(self, identifiers: list[str]) -> list[dict[str, Any]]:
        """Find nodes matching any identifier in a list of symbol names/qualified names/API paths."""
        query = """
        MATCH (s)
        WHERE s.name IN $ids OR s.qualified_name IN $ids OR s.symbol_id IN $ids
           OR (s:ApiEndpoint AND (s.endpoint_id IN $ids OR s.path IN $ids))
           OR (s:ApiClientCall AND (s.call_id IN $ids OR s.url IN $ids))
           OR (s:ApiContract AND (s.contract_id IN $ids OR s.path_template IN $ids))
        RETURN labels(s) AS labels, coalesce(s.symbol_id, s.endpoint_id, s.call_id, s.contract_id) AS symbol_id,
               s.name AS name, s.qualified_name AS qualified_name,
               s.file_path AS file_path, s.start_line AS start_line, s.end_line AS end_line,
               s.docstring AS docstring
        """
        return self.client.execute_read(query, {"ids": identifiers})

    def find_callers(self, symbol_name_or_qn: str) -> list[dict[str, Any]]:
        """Find functions or methods that call the specified symbol."""
        query = """
        MATCH (caller)-[r:CALLS]->(callee)
        WHERE callee.name = $name OR callee.qualified_name = $name OR callee.symbol_id = $name
        RETURN labels(caller) AS caller_type, caller.symbol_id AS caller_id, caller.name AS caller_name,
               caller.qualified_name AS caller_qn, caller.file_path AS file_path,
               caller.start_line AS start_line, caller.end_line AS end_line,
               r.line_number AS line_number
        """
        return self.client.execute_read(query, {"name": symbol_name_or_qn})

    def find_callees(self, symbol_name_or_qn: str) -> list[dict[str, Any]]:
        """Find functions or methods called by the specified symbol."""
        query = """
        MATCH (caller)-[r:CALLS]->(callee)
        WHERE caller.name = $name OR caller.qualified_name = $name OR caller.symbol_id = $name
        RETURN labels(callee) AS callee_type, callee.symbol_id AS callee_id, callee.name AS callee_name,
               callee.qualified_name AS callee_qn, callee.file_path AS file_path,
               callee.start_line AS start_line, callee.end_line AS end_line,
               r.line_number AS line_number
        """
        return self.client.execute_read(query, {"name": symbol_name_or_qn})

    def find_dependencies(self, symbol_name_or_qn: str) -> list[dict[str, Any]]:
        """Find outgoing dependencies (calls, imports, inheritance) of a symbol."""
        query = """
        MATCH (s)-[r]->(target)
        WHERE s.name = $name OR s.qualified_name = $name OR s.symbol_id = $name
        RETURN type(r) AS relationship, labels(target) AS target_type,
               target.symbol_id AS target_id, target.name AS target_name,
               target.qualified_name AS target_qn, target.file_path AS file_path,
               target.start_line AS start_line, target.end_line AS end_line
        """
        return self.client.execute_read(query, {"name": symbol_name_or_qn})

    def find_dependents(self, symbol_name_or_qn: str) -> list[dict[str, Any]]:
        """Find incoming dependents that rely on the specified symbol."""
        query = """
        MATCH (source)-[r]->(s)
        WHERE s.name = $name OR s.qualified_name = $name OR s.symbol_id = $name
        RETURN type(r) AS relationship, labels(source) AS source_type,
               source.symbol_id AS source_id, source.name AS source_name,
               source.qualified_name AS source_qn, source.file_path AS file_path,
               source.start_line AS start_line, source.end_line AS end_line
        """
        return self.client.execute_read(query, {"name": symbol_name_or_qn})

    def find_imports(self, symbol_name_or_file: str) -> list[dict[str, Any]]:
        """Find imports related to a symbol or file path."""
        query = """
        MATCH (source)-[r:IMPORTS]->(target)
        WHERE source.name = $id OR source.qualified_name = $id OR source.file_path = $id
           OR target.name = $id OR target.qualified_name = $id OR target.file_path = $id
        RETURN source.qualified_name AS source_qn, source.file_path AS source_file,
               target.qualified_name AS target_qn, target.file_path AS target_file
        """
        return self.client.execute_read(query, {"id": symbol_name_or_file})

    def find_inheritance_chain(self, class_name: str) -> list[dict[str, Any]]:
        """Find complete class hierarchy (superclasses and subclasses)."""
        query = """
        MATCH path = (child:Class)-[:INHERITS*1..5]->(parent:Class)
        WHERE child.name = $name OR child.qualified_name = $name OR parent.name = $name OR parent.qualified_name = $name
        RETURN [node in nodes(path) | node.qualified_name] AS hierarchy
        """
        return self.client.execute_read(query, {"name": class_name})

    def find_related_symbols(self, symbol_name_or_qn: str, max_hops: int = 2) -> list[dict[str, Any]]:
        """Find 1 to N-hop connected symbols around a target entity."""
        hops = max(1, min(max_hops, 5))
        query = f"""
        MATCH path = (s)-[*1..{hops}]-(related)
        WHERE s.name = $name OR s.qualified_name = $name OR s.symbol_id = $name
        RETURN DISTINCT labels(related) AS labels, related.symbol_id AS symbol_id,
               related.name AS name, related.qualified_name AS qualified_name,
               related.file_path AS file_path, related.start_line AS start_line,
               related.end_line AS end_line, length(path) AS distance
        ORDER BY distance ASC
        LIMIT 30
        """
        return self.client.execute_read(query, {"name": symbol_name_or_qn})

    def find_paths(self, source_name: str, target_name: str, max_hops: int = 3) -> list[dict[str, Any]]:
        """Find paths connecting source and target symbols up to max_hops."""
        hops = max(1, min(max_hops, 5))
        query = f"""
        MATCH path = (source)-[*1..{hops}]->(target)
        WHERE (source.name = $src OR source.qualified_name = $src OR source.symbol_id = $src)
          AND (target.name = $tgt OR target.qualified_name = $tgt OR target.symbol_id = $tgt)
        RETURN [node in nodes(path) | {{
            name: node.name,
            qualified_name: node.qualified_name,
            file_path: node.file_path,
            symbol_id: node.symbol_id,
            labels: labels(node)
        }}] AS path_nodes,
        [rel in relationships(path) | type(rel)] AS path_relationships,
        length(path) AS hop_count
        LIMIT 10
        """
        return self.client.execute_read(query, {"src": source_name, "tgt": target_name})

    def find_shortest_path(self, source_name: str, target_name: str) -> list[dict[str, Any]]:
        """Find the shortest path connecting source and target symbols."""
        query = """
        MATCH (source), (target)
        WHERE (source.name = $src OR source.qualified_name = $src OR source.symbol_id = $src)
          AND (target.name = $tgt OR target.qualified_name = $tgt OR target.symbol_id = $tgt)
        MATCH path = shortestPath((source)-[*1..6]-(target))
        RETURN [node in nodes(path) | {
            name: node.name,
            qualified_name: node.qualified_name,
            file_path: node.file_path,
            symbol_id: node.symbol_id,
            labels: labels(node)
        }] AS path_nodes,
        [rel in relationships(path) | type(rel)] AS path_relationships,
        length(path) AS hop_count
        """
        return self.client.execute_read(query, {"src": source_name, "tgt": target_name})

    def find_impact_subgraph(self, symbol_name_or_qn: str, max_depth: int = 2) -> list[dict[str, Any]]:
        """Find impacted components up to max_depth hops when a symbol changes."""
        hops = max(1, min(max_depth, 5))
        query = f"""
        MATCH path = (impacted)-[*1..{hops}]->(target)
        WHERE target.name = $name OR target.qualified_name = $name OR target.symbol_id = $name
        RETURN [node in nodes(path) | {{
            name: node.name,
            qualified_name: node.qualified_name,
            file_path: node.file_path,
            symbol_id: node.symbol_id,
            labels: labels(node)
        }}] AS path_nodes,
        [rel in relationships(path) | type(rel)] AS path_relationships,
        length(path) AS hop_count
        LIMIT 25
        """
        return self.client.execute_read(query, {"name": symbol_name_or_qn})

    def find_transitive_dependents(
        self, symbol_name_or_qn: str, max_hops: int = 2, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Find nodes that depend directly or transitively on the target symbol (Upstream Impact)."""
        hops = max(1, min(max_hops, 5))
        limit_val = max(1, min(limit, 500))
        query = f"""
        MATCH path = (source)-[*1..{hops}]->(target)
        WHERE target.name = $name OR target.qualified_name = $name OR target.symbol_id = $name
        RETURN labels(source) AS labels, source.symbol_id AS symbol_id, source.name AS name,
               source.qualified_name AS qualified_name, source.file_path AS file_path,
               source.start_line AS start_line, source.end_line AS end_line,
               length(path) AS hop_count,
               [rel in relationships(path) | type(rel)] AS rel_types,
               [node in nodes(path) | node.qualified_name] AS path_nodes,
               [node in nodes(path) | node.file_path] AS path_files
        LIMIT {limit_val}
        """
        return self.client.execute_read(query, {"name": symbol_name_or_qn})

    def find_transitive_dependencies(
        self, symbol_name_or_qn: str, max_hops: int = 2, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Find nodes that the target symbol directly or transitively depends on (Downstream Impact)."""
        hops = max(1, min(max_hops, 5))
        limit_val = max(1, min(limit, 500))
        query = f"""
        MATCH path = (source)-[*1..{hops}]->(target)
        WHERE source.name = $name OR source.qualified_name = $name OR source.symbol_id = $name
        RETURN labels(target) AS labels, target.symbol_id AS symbol_id, target.name AS name,
               target.qualified_name AS qualified_name, target.file_path AS file_path,
               target.start_line AS start_line, target.end_line AS end_line,
               length(path) AS hop_count,
               [rel in relationships(path) | type(rel)] AS rel_types,
               [node in nodes(path) | node.qualified_name] AS path_nodes,
               [node in nodes(path) | node.file_path] AS path_files
        LIMIT {limit_val}
        """
        return self.client.execute_read(query, {"name": symbol_name_or_qn})

    def find_api_flow(self, identifier: str, max_hops: int = 3) -> list[dict[str, Any]]:
        """Traverse cross-language API relationships connecting client calls, endpoints, contracts, and controllers."""
        hops = max(1, min(max_hops, 5))
        query = f"""
        MATCH path = (n)-[*1..{hops}]-(m)
        WHERE n.name CONTAINS $id OR n.qualified_name CONTAINS $id
           OR (n:ApiEndpoint AND (n.endpoint_id = $id OR n.path = $id))
           OR (n:ApiClientCall AND (n.call_id = $id OR n.url = $id))
           OR (n:ApiContract AND (n.contract_id = $id OR n.path_template = $id))
        RETURN [node in nodes(path) | {{
            name: node.name,
            qualified_name: node.qualified_name,
            file_path: node.file_path,
            symbol_id: coalesce(node.symbol_id, node.endpoint_id, node.call_id, node.contract_id),
            labels: labels(node),
            start_line: node.start_line,
            end_line: node.end_line
        }}] AS path_nodes,
        [rel in relationships(path) | type(rel)] AS path_relationships,
        length(path) AS hop_count
        LIMIT 20
        """
        return self.client.execute_read(query, {"id": identifier})


