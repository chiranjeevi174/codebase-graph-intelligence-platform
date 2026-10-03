"""Graph retrieval and visualization metadata endpoint."""

from fastapi import APIRouter

from app.graph.neo4j_client import Neo4jClient

router = APIRouter(prefix="/graph", tags=["Graph"])


@router.get("/{repository_id}")
def get_repository_graph_summary(repository_id: str, limit: int = 150):
    """Retrieve graph nodes, relationships, and distribution statistics for specified repository."""
    client = Neo4jClient()
    try:
        nodes_query = """
        MATCH (r:Repository {repository_id: $repo_id})-[*1..2]->(n)
        RETURN labels(n)[0] AS label, count(n) AS count
        """
        node_counts = client.execute_read(nodes_query, {"repo_id": repository_id})

        rels_query = """
        MATCH (r:Repository {repository_id: $repo_id})-[*1..2]->(n)-[rel]->(m)
        RETURN type(rel) AS relationship, count(rel) AS count
        """
        rel_counts = client.execute_read(rels_query, {"repo_id": repository_id})

        node_list_query = """
        MATCH (r:Repository {repository_id: $repo_id})-[*1..2]->(n)
        RETURN coalesce(n.symbol_id, n.endpoint_id, n.call_id, n.contract_id, n.file_path, elementId(n)) AS id,
               labels(n)[0] AS label,
               coalesce(n.name, n.symbol_name, n.path, n.url, n.path_template, n.relative_path, "Node") AS name,
               coalesce(n.qualified_name, n.file_path, "") AS qualified_name,
               n.file_path AS file_path,
               n.language AS language,
               n.symbol_type AS symbol_type,
               n.start_line AS start_line,
               n.end_line AS end_line
        LIMIT $limit
        """
        node_rows = client.execute_read(node_list_query, {"repo_id": repository_id, "limit": limit})

        rel_list_query = """
        MATCH (r:Repository {repository_id: $repo_id})-[*1..2]->(n)-[rel]->(m)
        RETURN coalesce(rel.rel_id, elementId(rel)) AS id,
               coalesce(n.symbol_id, n.endpoint_id, n.call_id, n.contract_id, n.file_path, elementId(n)) AS source,
               coalesce(m.symbol_id, m.endpoint_id, m.call_id, m.contract_id, m.file_path, elementId(m)) AS target,
               type(rel) AS type
        LIMIT $limit
        """
        rel_rows = client.execute_read(rel_list_query, {"repo_id": repository_id, "limit": limit})

        node_dist = {item["label"]: item["count"] for item in node_counts if "label" in item}
        rel_dist = {item["relationship"]: item["count"] for item in rel_counts if "relationship" in item}

        return {
            "repository_id": repository_id,
            "node_distribution": node_dist,
            "relationship_distribution": rel_dist,
            "nodes": node_rows,
            "relationships": rel_rows,
            "metadata": {
                "total_nodes": sum(node_dist.values()),
                "total_relationships": sum(rel_dist.values()),
                "rendered_nodes": len(node_rows),
                "rendered_relationships": len(rel_rows),
                "limit": limit,
            },
        }
    except Exception as e:
        return {
            "repository_id": repository_id,
            "status": "graph_unavailable",
            "message": str(e),
            "node_distribution": {},
            "relationship_distribution": {},
            "nodes": [],
            "relationships": [],
            "metadata": {"limit": limit},
        }
