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
    ) -> FocusedSubgraph:
        """Extract multi-hop neighborhood graph around a seed symbol with bounded limits."""
        hops = max(1, min(max_hops, 5))
        query = f"""
        MATCH path = (center)-[r*1..{hops}]-(neighbor)
        WHERE center.name = $id OR center.qualified_name = $id OR center.symbol_id = $id
        RETURN nodes(path) AS nodes, relationships(path) AS relationships
        LIMIT {max_relationships}
        """

        nodes_dict: dict[str, SubgraphNode] = {}
        edges_list: list[SubgraphEdge] = []
        paths_list: list[GraphPath] = []
        seen_edges: set[tuple[str, str, str]] = set()

        try:
            records = self.client.execute_read(query, {"id": symbol_identifier})
            for record in records:
                path_nodes = record.get("nodes", [])
                path_rels = record.get("relationships", [])

                path_node_objs: list[GraphNode] = []
                for n in path_nodes:
                    node_id = str(n.get("symbol_id") or n.get("file_id") or n.get("name") or id(n))
                    if len(nodes_dict) < max_nodes and node_id not in nodes_dict:
                        nodes_dict[node_id] = SubgraphNode(
                            id=node_id,
                            name=n.get("name", "Unknown"),
                            qualified_name=n.get("qualified_name"),
                            labels=list(n.labels) if hasattr(n, "labels") else [],
                            file_path=n.get("file_path"),
                            start_line=n.get("start_line"),
                            end_line=n.get("end_line"),
                            docstring=n.get("docstring"),
                        )

                    path_node_objs.append(
                        GraphNode(
                            id=node_id,
                            name=n.get("name", "Unknown"),
                            qualified_name=n.get("qualified_name"),
                            labels=list(n.labels) if hasattr(n, "labels") else [],
                            file_path=n.get("file_path"),
                            start_line=n.get("start_line"),
                            end_line=n.get("end_line"),
                            docstring=n.get("docstring"),
                        )
                    )

                path_rel_types: list[str] = []
                for rel in path_rels:
                    rel_type = rel.type if hasattr(rel, "type") else "RELATED"
                    path_rel_types.append(rel_type)
                    start_node = rel.start_node if hasattr(rel, "start_node") else None
                    end_node = rel.end_node if hasattr(rel, "end_node") else None
                    if start_node and end_node and len(edges_list) < max_relationships:
                        src_id = str(start_node.get("symbol_id") or start_node.get("name") or id(start_node))
                        tgt_id = str(end_node.get("symbol_id") or end_node.get("name") or id(end_node))
                        edge_key = (src_id, tgt_id, rel_type)
                        if edge_key not in seen_edges:
                            seen_edges.add(edge_key)
                            edges_list.append(
                                SubgraphEdge(
                                    source_id=src_id,
                                    target_id=tgt_id,
                                    relationship_type=rel_type,
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

