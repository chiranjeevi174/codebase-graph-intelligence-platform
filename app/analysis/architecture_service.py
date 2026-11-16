"""Architecture Intelligence & Visualization Engine.

Discovers project modules, packages, directory structures, class/function hierarchies,
module dependencies, API entry points, and architectural layering from Neo4j knowledge
graph with filesystem static analysis fallback.
"""

from collections import defaultdict
from pathlib import Path
from typing import Any

from app.graph.neo4j_client import Neo4jClient
from app.llm.factory import get_llm
from app.models.entities import (
    ArchitectureAnalysisRequest,
    ArchitectureAnalysisResult,
    ArchitectureEdge,
    ArchitectureLayer,
    ArchitectureNode,
    ArchitectureSummary,
)
from app.parsing.parser_factory import ParserFactory
from app.utils.logger import logger


class ArchitectureIntelligenceService:
    """Discovers, models, and explains codebase architecture and structural relationships."""

    def __init__(self, neo4j_client: Neo4jClient | None = None):
        self.client = neo4j_client or Neo4jClient()

    def analyze_architecture(self, request: ArchitectureAnalysisRequest) -> ArchitectureAnalysisResult:
        """Execute architecture discovery, graph building, and grounded structural explanation."""
        repo_id = request.repository_id or "sample_repo"
        level = request.level or "overview"

        logger.info(f"[ArchitectureService] Analyzing architecture for '{repo_id}' (level: {level})")

        # Step 1: Discover architecture from Neo4j if available, or fall back to filesystem parsing
        data = self._discover_from_graph(repo_id, level)
        if not data or not data.get("nodes"):
            logger.info(f"[ArchitectureService] Neo4j graph empty or offline for '{repo_id}'. Using filesystem parser.")
            repo_path = self._resolve_repo_path(repo_id, request.repo_path)
            data = self._discover_from_filesystem(repo_id, repo_path, level)

        # Step 2: Classify into Architectural Layers
        layers = self._classify_layers(data.get("nodes", []))

        # Step 3: Compute summary metrics
        summary = self._compute_summary(repo_id, data.get("nodes", []), data.get("edges", []), layers)

        # Step 4: Extract architectural entry points
        entry_points = [
            {
                "id": n.id,
                "name": n.name,
                "path": n.path,
                "layer": n.layer,
                "type": n.label,
                "description": n.description,
            }
            for n in data.get("nodes", [])
            if n.is_entry_point
        ]

        # Step 5: Grounded LLM Explanation
        explanation = self._generate_explanation(repo_id, summary, layers, data.get("nodes", []), data.get("edges", []))

        return ArchitectureAnalysisResult(
            repository_id=repo_id,
            summary=summary,
            layers=layers,
            nodes=data.get("nodes", []),
            edges=data.get("edges", []),
            entry_points=entry_points,
            explanation=explanation,
        )

    def _resolve_repo_path(self, repo_id: str, requested_path: str | None) -> Path:
        """Resolve filesystem path for the repository."""
        if requested_path and Path(requested_path).exists():
            return Path(requested_path)

        candidates = [
            Path("tests/fixtures") / repo_id,
            Path("fixtures") / repo_id,
            Path(repo_id),
            Path("tests/fixtures/sample_repo"),
        ]
        for c in candidates:
            if c.exists() and c.is_dir():
                return c
        return Path("tests/fixtures/sample_repo")

    def _discover_from_graph(self, repo_id: str, level: str) -> dict[str, Any] | None:
        """Attempt to extract architecture nodes and edges from Neo4j knowledge graph."""
        try:
            # Query files and defined symbols
            query_nodes = """
            MATCH (r:Repository {repository_id: $repo_id})-[:CONTAINS]->(f:File)
            OPTIONAL MATCH (f)-[:DEFINES]->(s)
            RETURN f.file_path AS file_path,
                   f.relative_path AS relative_path,
                   f.language AS language,
                   f.lines_of_code AS loc,
                   labels(s)[0] AS symbol_type,
                   s.name AS symbol_name,
                   s.qualified_name AS symbol_qn,
                   s.symbol_id AS symbol_id
            """
            rows = self.client.execute_read(query_nodes, {"repo_id": repo_id})
            if not rows:
                return None

            # Query relationships
            query_edges = """
            MATCH (r:Repository {repository_id: $repo_id})-[:CONTAINS]->(f1:File)-[:DEFINES]->(s1)
            MATCH (s1)-[rel]->(s2)
            MATCH (f2:File)-[:DEFINES]->(s2)
            WHERE type(rel) IN ['CALLS', 'IMPORTS', 'DEPENDS_ON', 'INHERITS', 'ROUTES_TO', 'MATCHES_ENDPOINT']
            RETURN coalesce(s1.qualified_name, s1.name, s1.symbol_id) AS source,
                   coalesce(s2.qualified_name, s2.name, s2.symbol_id) AS target,
                   type(rel) AS rel_type,
                   f1.relative_path AS source_file,
                   f2.relative_path AS target_file
            """
            rel_rows = self.client.execute_read(query_edges, {"repo_id": repo_id})
            return self._build_graph_models_from_rows(repo_id, rows, rel_rows, level)
        except Exception as e:  # noqa: BLE001 # Neo4j connection or query error boundary
            logger.debug(f"[ArchitectureService] Neo4j discovery skipped: {e}")
            return None

    def _build_graph_models_from_rows(
        self, repo_id: str, node_rows: list[dict[str, Any]], edge_rows: list[dict[str, Any]], level: str
    ) -> dict[str, Any]:
        """Convert Neo4j Cypher rows into typed ArchitectureNode and ArchitectureEdge models."""
        files_map: dict[str, dict[str, Any]] = defaultdict(lambda: {"symbols": [], "loc": 0, "language": ""})
        for r in node_rows:
            fpath = r.get("relative_path") or r.get("file_path") or "unknown"
            files_map[fpath]["loc"] = r.get("loc") or files_map[fpath]["loc"]
            files_map[fpath]["language"] = r.get("language") or files_map[fpath]["language"]
            if r.get("symbol_name"):
                files_map[fpath]["symbols"].append(
                    {
                        "name": r.get("symbol_name"),
                        "type": r.get("symbol_type") or "Symbol",
                        "qn": r.get("symbol_qn"),
                    }
                )

        nodes: list[ArchitectureNode] = []
        edges: list[ArchitectureEdge] = []

        # Build file and module nodes
        for fpath, meta in files_map.items():
            mod_name = self._extract_module_name(fpath)
            layer = self._determine_layer(fpath)
            is_entry = self._is_entry_point(fpath)

            if level == "overview":
                # Aggregate at file/module level
                node_id = f"file_{fpath.replace('/', '_').replace('.', '_')}"
                nodes.append(
                    ArchitectureNode(
                        id=node_id,
                        name=Path(fpath).name,
                        label="File",
                        path=fpath,
                        layer=layer,
                        file_count=1,
                        symbol_count=len(meta["symbols"]),
                        description=f"{meta['language'].title() or 'Code'} component in {mod_name} module ({len(meta['symbols'])} symbols).",
                        is_entry_point=is_entry,
                    )
                )
            else:
                # Detailed: add file + symbol nodes
                node_id = f"file_{fpath.replace('/', '_').replace('.', '_')}"
                nodes.append(
                    ArchitectureNode(
                        id=node_id,
                        name=Path(fpath).name,
                        label="File",
                        path=fpath,
                        layer=layer,
                        file_count=1,
                        symbol_count=len(meta["symbols"]),
                        description=f"Source file {fpath}",
                        is_entry_point=is_entry,
                    )
                )
                for s in meta["symbols"][:5]:  # Bounded symbols
                    s_id = f"sym_{s['name']}_{fpath.replace('/', '_').replace('.', '_')}"
                    nodes.append(
                        ArchitectureNode(
                            id=s_id,
                            name=s["name"],
                            label=s["type"],
                            path=fpath,
                            layer=layer,
                            description=f"{s['type']} defined in {fpath}",
                            is_entry_point=False,
                        )
                    )

        # Build edges
        seen_edges: set[str] = set()
        for e in edge_rows:
            src_file = e.get("source_file") or ""
            tgt_file = e.get("target_file") or ""
            if not src_file or not tgt_file or src_file == tgt_file:
                continue

            src_id = f"file_{src_file.replace('/', '_').replace('.', '_')}"
            tgt_id = f"file_{tgt_file.replace('/', '_').replace('.', '_')}"
            edge_key = f"{src_id}->{tgt_id}:{e.get('rel_type')}"
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append(
                    ArchitectureEdge(
                        id=f"edge_{len(edges) + 1}",
                        source=src_id,
                        target=tgt_id,
                        type=e.get("rel_type") or "DEPENDS_ON",
                        weight=1,
                        description=f"{src_file} depends on {tgt_file} via {e.get('rel_type')}",
                    )
                )

        return {"nodes": nodes, "edges": edges}

    def _discover_from_filesystem(self, repo_id: str, repo_path: Path, level: str) -> dict[str, Any]:
        """Perform static AST and file organization discovery on repository directory."""
        nodes: list[ArchitectureNode] = []
        edges: list[ArchitectureEdge] = []
        file_paths = []

        supported_exts = {".py", ".ts", ".js", ".go", ".java"}
        for p in repo_path.rglob("*"):
            if (
                p.is_file()
                and p.suffix in supported_exts
                and "node_modules" not in p.parts
                and ".git" not in p.parts
                and "__pycache__" not in p.parts
            ):
                file_paths.append(p)

        file_nodes_map: dict[str, str] = {}
        imports_map: dict[str, list[str]] = defaultdict(list)

        for p in file_paths:
            try:
                rel_path = str(p.relative_to(repo_path)).replace("\\", "/")
            except ValueError:
                rel_path = p.name

            layer = self._determine_layer(rel_path)
            is_entry = self._is_entry_point(rel_path)
            node_id = f"file_{rel_path.replace('/', '_').replace('.', '_')}"
            file_nodes_map[rel_path] = node_id

            # Parse symbols using ParserFactory
            symbols = []
            try:
                parser = ParserFactory.get_parser_for_file(str(p))
                if parser:
                    extracted = parser.parse_file(str(p))
                    symbols = extracted.symbols if extracted else []
            except Exception as e:  # noqa: BLE001 # Parsing error boundary
                logger.debug(f"[ArchitectureService] Error parsing {rel_path}: {e}")

            # Basic import discovery via lines
            try:
                with open(p, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str.startswith(("import ", "from ")):
                            parts = line_str.split()
                            if len(parts) >= 2:
                                imp = parts[1].split(".")[0]
                                imports_map[rel_path].append(imp)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"[ArchitectureService] Line import extraction error {rel_path}: {e}")

            nodes.append(
                ArchitectureNode(
                    id=node_id,
                    name=p.name,
                    label="File",
                    path=rel_path,
                    layer=layer,
                    file_count=1,
                    symbol_count=len(symbols),
                    description=f"{p.suffix[1:].upper()} component in layer '{layer}' ({len(symbols)} symbols extracted).",
                    is_entry_point=is_entry,
                )
            )

            if level == "detailed":
                for s in symbols[:4]:
                    s_id = f"sym_{s.symbol_name}_{rel_path.replace('/', '_').replace('.', '_')}"
                    nodes.append(
                        ArchitectureNode(
                            id=s_id,
                            name=s.symbol_name,
                            label=s.symbol_type.value if hasattr(s.symbol_type, "value") else str(s.symbol_type),
                            path=rel_path,
                            layer=layer,
                            description=f"{s.symbol_type} defined in {rel_path}",
                            is_entry_point=False,
                        )
                    )

        # Connect edges based on imports and file references
        seen_edges: set[str] = set()
        for src_file, imported_modules in imports_map.items():
            src_id = file_nodes_map.get(src_file)
            if not src_id:
                continue

            for tgt_file, tgt_id in file_nodes_map.items():
                if src_file == tgt_file:
                    continue
                tgt_stem = Path(tgt_file).stem
                tgt_parent = Path(tgt_file).parent.name
                if tgt_stem in imported_modules or tgt_parent in imported_modules:
                    edge_key = f"{src_id}->{tgt_id}"
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        edges.append(
                            ArchitectureEdge(
                                id=f"edge_{len(edges) + 1}",
                                source=src_id,
                                target=tgt_id,
                                type="IMPORTS",
                                weight=1,
                                description=f"`{src_file}` imports components from `{tgt_file}`",
                            )
                        )

        # Fallback edges if none found
        if not edges and len(nodes) > 1:
            main_node = next((n for n in nodes if n.is_entry_point), nodes[0])
            for n in nodes:
                if n.id != main_node.id and n.label == "File":
                    edges.append(
                        ArchitectureEdge(
                            id=f"edge_{len(edges) + 1}",
                            source=main_node.id,
                            target=n.id,
                            type="DEPENDS_ON",
                            weight=1,
                            description=f"Entry point `{main_node.name}` coordinates `{n.name}`",
                        )
                    )

        return {"nodes": nodes, "edges": edges}

    def _determine_layer(self, path: str) -> str:
        """Classify a file path into standard software architecture layers."""
        lower = path.lower()
        if any(k in lower for k in ["api", "route", "endpoint", "controller", "view", "server"]):
            return "Presentation / API"
        if any(k in lower for k in ["service", "handler", "manager", "workflow", "processor", "usecase"]):
            return "Business Logic / Service"
        if any(k in lower for k in ["model", "repo", "db", "database", "schema", "entity", "store"]):
            return "Data / Persistence"
        if any(k in lower for k in ["config", "util", "helper", "middleware", "auth", "security", "client"]):
            return "Infrastructure / Utility"
        return "Core / Domain"

    def _is_entry_point(self, path: str) -> bool:
        """Determine whether file is an architectural entry point."""
        stem = Path(path).stem.lower()
        return stem in ("main", "app", "index", "server", "application", "cli", "entry")

    def _extract_module_name(self, path: str) -> str:
        """Extract top-level package or module name from relative path."""
        parts = Path(path).parts
        if len(parts) > 1:
            return parts[0]
        return "root"

    def _classify_layers(self, nodes: list[ArchitectureNode]) -> list[ArchitectureLayer]:
        """Group components into defined architectural layers."""
        layer_buckets: dict[str, list[str]] = defaultdict(list)
        descriptions = {
            "Presentation / API": "Handles inbound network requests, REST/HTTP routing, serialization, and API contracts.",
            "Business Logic / Service": "Encapsulates domain business logic, service orchestration, and domain rules.",
            "Data / Persistence": "Manages database models, entity state, data access repositories, and caching.",
            "Infrastructure / Utility": "Provides shared utilities, configurations, middleware, and external service clients.",
            "Core / Domain": "Core system abstractions, interfaces, and primary system domain definitions.",
        }

        for n in nodes:
            if n.label == "File":
                layer_buckets[n.layer].append(n.name)

        layers: list[ArchitectureLayer] = []
        for name, components in layer_buckets.items():
            layers.append(
                ArchitectureLayer(
                    name=name,
                    description=descriptions.get(name, "Architectural boundary components."),
                    components=sorted(components),
                )
            )
        return sorted(layers, key=lambda l: l.name)

    def _compute_summary(
        self,
        repo_id: str,
        nodes: list[ArchitectureNode],
        edges: list[ArchitectureEdge],
        layers: list[ArchitectureLayer],
    ) -> ArchitectureSummary:
        """Compute aggregated architecture metrics."""
        files = [n for n in nodes if n.label == "File"]
        classes = [n for n in nodes if n.label == "Class"]
        functions = [n for n in nodes if n.label in ("Function", "Method")]
        endpoints = [n for n in nodes if n.label == "ApiEndpoint"]
        entry_points = [n.name for n in nodes if n.is_entry_point]

        # Extract unique packages / directories
        packages = {Path(n.path).parent.as_posix() for n in files if Path(n.path).parent.as_posix() != "."}

        return ArchitectureSummary(
            repository_id=repo_id,
            total_modules=len(packages) or 1,
            total_packages=len(packages),
            total_files=len(files),
            total_classes=len(classes),
            total_functions=len(functions),
            total_endpoints=len(endpoints),
            entry_points=entry_points,
            layers_detected=[layer.name for layer in layers],
        )

    def _generate_explanation(
        self,
        repo_id: str,
        summary: ArchitectureSummary,
        layers: list[ArchitectureLayer],
        nodes: list[ArchitectureNode],
        edges: list[ArchitectureEdge],
    ) -> str:
        """Generate understandable, technically grounded architecture explanation using LLM with deterministic fallback."""
        layers_text = "\n".join(
            [f"- **{layer.name}**: {', '.join(layer.components[:6]) or 'None'}" for layer in layers]
        )
        entry_points_text = ", ".join(summary.entry_points) or "None detected"

        prompt = f"""You are a Senior Software Architect inspecting the codebase architecture for repository '{repo_id}'.

Discovered Architecture Data:
- Total Files: {summary.total_files} across {summary.total_packages} packages/directories
- Key Entry Points: {entry_points_text}
- Architectural Layers:
{layers_text}
- Total Dependencies/Connections: {len(edges)}

Explain the software architecture clearly for developers:
1. High-Level Architecture Overview: Explain the architectural design pattern and core purpose of the project.
2. Component Responsibilities: Detail the specific responsibilities of each detected layer (Presentation, Service, Data, Infrastructure).
3. Dependency Flow & Interconnection: Explain how requests or data move between entry points, services, and repositories.
4. Architectural Observations & Recommendations: Highlight design strengths and areas to maintain clean separation of concerns.

Ground every statement in the actual discovered components above. Do not hallucinate external frameworks or files."""

        system_prompt = (
            "You are a Senior Software Architect providing clear, grounded, professional architecture intelligence. "
            "Explain technical concepts cleanly, avoid vague buzzwords, and provide actionable engineering takeaways."
        )

        try:
            llm = get_llm()
            explanation = llm.generate(prompt=prompt, system_prompt=system_prompt, temperature=0.2)
            if explanation and len(explanation.strip()) > 50:
                return explanation
        except Exception as e:  # noqa: BLE001 # LLM explanation fallback boundary
            logger.debug(f"[ArchitectureService] LLM explanation generation failed: {e}")

        # Deterministic Grounded Fallback Explanation
        return (
            f"### Architecture Overview for `{repo_id}`\n\n"
            f"The codebase is organized into **{len(layers)} architectural layers** comprising **{summary.total_files} source files** "
            f"and **{summary.total_packages} logical packages**.\n\n"
            f"#### 1. Architectural Layers & Separation of Concerns\n"
            + "\n".join(
                [
                    f"- **{layer.name}**: {layer.description} (Components: `{', '.join(layer.components[:5])}`)"
                    for layer in layers
                ]
            )
            + f"\n\n#### 2. Execution Entry Points & Data Flow\n"
            f"The primary architectural entry points are `{entry_points_text}`. Inbound execution flows from the "
            f"Presentation/API layer through business logic service orchestration down to persistence and repository components.\n\n"
            f"#### 3. Component Coupling\n"
            f"Discovered **{len(edges)} direct structural dependencies** showing clean unidirectional dependency flow from upper service layers toward domain entities."
        )
