"""Subgraph Builder for constructing focused contextual graph neighborhoods."""

from typing import Any

from pydantic import BaseModel, Field

from app.graph.neo4j_client import Neo4jClient
from app.models.entities import GraphNode, GraphPath
from app.utils.logger import logger


class SubgraphNode(BaseModel):
    id: str
    name: str
    qualified_name: str | None = None
    labels: list[str]
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    docstring: str | None = None


class SubgraphEdge(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class FocusedSubgraph(BaseModel):
    center_symbol: str
    max_hops: int
    nodes: list[SubgraphNode] = Field(default_factory=list)
    edges: list[SubgraphEdge] = Field(default_factory=list)
    paths: list[GraphPath] = Field(default_factory=list)


class SubgraphBuilder:
    """Extracts a bounded contextual subgraph around candidate target entities."""

    def __init__(self, client: Neo4jClient | None = None):
        self.client = client or Neo4jClient()

    def build_subgraph(
        self,
        symbol_identifier: str,
        max_hops: int = 2,
        max_nodes: int = 50,
        max_relationships: int = 100,
        repository_id: str | None = None,
    ) -> FocusedSubgraph:
        """Extract multi-hop neighborhood graph around a seed symbol with bounded limits."""
        hops = max(1, min(max_hops, 5))
        query = f"""
        MATCH (center)
        WHERE (
            center.name = $id 
            OR center.qualified_name = $id 
            OR center.symbol_id = $id
            OR center.file_path = $id
            OR center.relative_path = $id
            OR center.file_id = $id
            OR toLower(center.name) = toLower($id)
            OR toLower(center.qualified_name) = toLower($id)
            OR (center:ApiEndpoint AND (center.endpoint_id = $id OR center.path = $id OR center.path ENDS WITH $id OR toLower(center.name) CONTAINS toLower($id)))
            OR (center:ApiClientCall AND (center.call_id = $id OR center.url = $id))
            OR (center:ApiContract AND (center.contract_id = $id OR center.path_template = $id))
        )
        AND ($repo_id IS NULL OR center.repository_id = $repo_id OR center.file_path CONTAINS $repo_id)
        WITH center LIMIT 10
        MATCH path = (center)-[r*1..{hops}]-(neighbor)
        WHERE ($repo_id IS NULL OR neighbor.repository_id = $repo_id OR neighbor.file_path CONTAINS $repo_id)
        RETURN nodes(path) AS nodes, relationships(path) AS relationships
        LIMIT {max_relationships}
        """

        nodes_dict: dict[str, SubgraphNode] = {}
        edges_list: list[SubgraphEdge] = []
        paths_list: list[GraphPath] = []
        seen_edges: set[tuple[str, str, str]] = set()

        try:
            records = self.client.execute_read(query, {"id": symbol_identifier, "repo_id": repository_id})
            for record in records:
                path_nodes = record.get("nodes", [])
                path_rels = record.get("relationships", [])

                path_node_objs: list[GraphNode] = []
                for n in path_nodes:
                    node_id = str(
                        n.get("symbol_id") or n.get("file_id") or n.get("name") or n.get("file_path") or id(n)
                    )
                    n_labels = (
                        list(n.labels)
                        if hasattr(n, "labels")
                        else (n.get("labels") if isinstance(n.get("labels"), list) else ["Symbol"])
                    )
                    if len(nodes_dict) < max_nodes and node_id not in nodes_dict:
                        nodes_dict[node_id] = SubgraphNode(
                            id=node_id,
                            name=n.get("name") or n.get("relative_path") or n.get("file_path") or "Unknown",
                            qualified_name=n.get("qualified_name") or n.get("file_path"),
                            labels=n_labels,
                            file_path=n.get("file_path") or n.get("relative_path"),
                            start_line=n.get("start_line"),
                            end_line=n.get("end_line"),
                            docstring=n.get("docstring"),
                        )

                    path_node_objs.append(
                        GraphNode(
                            id=node_id,
                            name=n.get("name") or n.get("relative_path") or n.get("file_path") or "Unknown",
                            qualified_name=n.get("qualified_name") or n.get("file_path"),
                            labels=n_labels,
                            file_path=n.get("file_path") or n.get("relative_path"),
                            start_line=n.get("start_line"),
                            end_line=n.get("end_line"),
                            docstring=n.get("docstring"),
                        )
                    )

                path_rel_types: list[str] = []
                for rel in path_rels:
                    if isinstance(rel, (tuple, list)) and len(rel) >= 2:
                        rel_type = str(rel[1])
                    elif hasattr(rel, "type"):
                        rel_type = str(rel.type)
                    elif isinstance(rel, dict) and "type" in rel:
                        rel_type = str(rel["type"])
                    else:
                        rel_type = "RELATED"
                    path_rel_types.append(rel_type)

                # Connect edges along path nodes
                for idx in range(len(path_node_objs) - 1):
                    if len(edges_list) >= max_relationships:
                        break
                    src_n = path_node_objs[idx]
                    tgt_n = path_node_objs[idx + 1]
                    r_type = path_rel_types[idx] if idx < len(path_rel_types) else "RELATED"
                    edge_key = (src_n.id, tgt_n.id, r_type)
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        edges_list.append(
                            SubgraphEdge(
                                source_id=src_n.id,
                                target_id=tgt_n.id,
                                relationship_type=r_type,
                            )
                        )

                if path_node_objs and len(paths_list) < 20:
                    src_node = path_node_objs[0]
                    tgt_node = path_node_objs[-1]
                    seq = []
                    for idx, node in enumerate(path_node_objs):
                        seq.append(node.qualified_name or node.name)
                        if idx < len(path_rel_types):
                            seq.append(f"-{path_rel_types[idx]}->")

                    paths_list.append(
                        GraphPath(
                            source_node=src_node,
                            target_node=tgt_node,
                            relationships=path_rel_types,
                            hop_count=len(path_rel_types),
                            path_sequence=seq,
                        )
                    )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Failed to build subgraph for symbol '{symbol_identifier}': {e}")

        return FocusedSubgraph(
            center_symbol=symbol_identifier,
            max_hops=hops,
            nodes=list(nodes_dict.values()),
            edges=edges_list,
            paths=paths_list,
        )
