"""Graph Builder for converting code intelligence data into Neo4j nodes and relationships."""

from app.graph.neo4j_client import Neo4jClient
from app.models.entities import ExtractedCodeData, RepositoryInfo
from app.utils.logger import logger


class GraphBuilder:
    """Ingests ExtractedCodeData objects and constructs Neo4j knowledge graph nodes and relationships."""

    def __init__(self, client: Neo4jClient | None = None):
        self.client = client or Neo4jClient()

    def create_repository_node(self, repo: RepositoryInfo):
        """Create or update Repository root node in Neo4j."""
        query = """
        MERGE (r:Repository {repository_id: $repository_id})
        SET r.name = $name,
            r.path = $path,
            r.commit_hash = $commit_hash,
            r.default_branch = $default_branch,
            r.total_files = $total_files,
            r.languages = $languages
        """
        self.client.execute_write(
            query,
            {
                "repository_id": repo.repository_id,
                "name": repo.name,
                "path": repo.path,
                "commit_hash": repo.commit_hash or "",
                "default_branch": repo.default_branch,
                "total_files": repo.total_files,
                "languages": repo.languages,
            },
        )

    def ingest_extracted_data(self, data: ExtractedCodeData):
        """Build graph entities and relationships for a single file's extracted data."""
        repo_id = data.repository_id
        file_info = data.file_info
        file_id = f"{repo_id}:{file_info.relative_path}"

        # 1. Create File node and link to Repository with CONTAINS
        file_query = """
        MERGE (r:Repository {repository_id: $repo_id})
        MERGE (f:File {file_id: $file_id})
        SET f.file_path = $file_path,
            f.relative_path = $relative_path,
            f.language = $language,
            f.lines_of_code = $lines_of_code,
            f.size_bytes = $size_bytes
        MERGE (r)-[:CONTAINS]->(f)
        """
        self.client.execute_write(
            file_query,
            {
                "repo_id": repo_id,
                "file_id": file_id,
                "file_path": file_info.file_path,
                "relative_path": file_info.relative_path,
                "language": file_info.language,
                "lines_of_code": file_info.lines_of_code,
                "size_bytes": file_info.size_bytes,
            },
        )

        # 2. Create Symbol nodes and link to File / Parent Symbol
        for symbol in data.symbols:
            label = symbol.symbol_type.value if hasattr(symbol.symbol_type, "value") else str(symbol.symbol_type)

            symbol_query = f"""
            MERGE (s:{label} {{symbol_id: $symbol_id}})
            SET s.name = $name,
                s.qualified_name = $qualified_name,
                s.file_path = $file_path,
                s.language = $language,
                s.start_line = $start_line,
                s.end_line = $end_line,
                s.docstring = $docstring
            """
            self.client.execute_write(
                symbol_query,
                {
                    "symbol_id": symbol.symbol_id,
                    "name": symbol.symbol_name,
                    "qualified_name": symbol.qualified_name,
                    "file_path": symbol.file_path,
                    "language": file_info.language,
                    "start_line": symbol.start_line,
                    "end_line": symbol.end_line,
                    "docstring": symbol.docstring or "",
                },
            )

            # Link File -> DEFINES -> Symbol
            defines_query = f"""
            MATCH (f:File {{file_id: $file_id}})
            MATCH (s:{label} {{symbol_id: $symbol_id}})
            MERGE (f)-[:DEFINES]->(s)
            """
            self.client.execute_write(defines_query, {"file_id": file_id, "symbol_id": symbol.symbol_id})

        # 3. Create IMPORTS relationships
        for imp in data.imports:
            imp_query = """
            MATCH (f:File {file_id: $file_id})
            MERGE (m:Module {name: $module_name})
            MERGE (f)-[r:IMPORTS]->(m)
            SET r.alias = $alias,
                r.imported_symbol = $imported_symbol,
                r.line_number = $line_number
            """
            self.client.execute_write(
                imp_query,
                {
                    "file_id": file_id,
                    "module_name": imp.module_name,
                    "alias": imp.alias or "",
                    "imported_symbol": imp.imported_symbol or "",
                    "line_number": imp.line_number,
                },
            )

        # 4. Create CALLS relationships
        for call in data.calls:
            call_query = """
            MATCH (caller {qualified_name: $caller_qn})
            MATCH (callee {name: $callee_name})
            MERGE (caller)-[r:CALLS]->(callee)
            SET r.line_number = $line_number,
                r.file_path = $file_path
            """
            try:
                self.client.execute_write(
                    call_query,
                    {
                        "caller_qn": call.caller_qualified_name,
                        "callee_name": call.callee_name,
                        "line_number": call.line_number,
                        "file_path": call.file_path,
                    },
                )
            except Exception as e:  # noqa: BLE001 # Partial graph ingestion fallback boundary
                logger.debug(
                    f"Failed to resolve CALLS relationship between {call.caller_qualified_name} -> {call.callee_name}: {e}"
                )

        # 5. Create INHERITS / IMPLEMENTS relationships
        for inh in data.inheritance:
            rel_type = getattr(inh, "relationship_type", "INHERITS")
            if rel_type not in ["INHERITS", "IMPLEMENTS"]:
                rel_type = "INHERITS"

            inh_query = f"""
            MATCH (child {{qualified_name: $child_qn}})
            MATCH (parent {{name: $parent_name}})
            MERGE (child)-[:{rel_type}]->(parent)
            """
            try:
                self.client.execute_write(
                    inh_query,
                    {
                        "child_qn": inh.child_qualified_name,
                        "parent_name": inh.parent_name,
                    },
                )
            except Exception as e:  # noqa: BLE001 # Partial graph ingestion fallback boundary
                logger.debug(f"Failed to link {rel_type} relation {inh.child_qualified_name} -> {inh.parent_name}: {e}")

        # 6. Create ApiEndpoint nodes
        for ep in data.api_endpoints:
            ep_query = """
            MATCH (f:File {file_id: $file_id})
            MERGE (e:ApiEndpoint {endpoint_id: $endpoint_id})
            SET e.repository_id = $repo_id,
                e.file_path = $file_path,
                e.language = $language,
                e.http_method = $http_method,
                e.path = $path,
                e.controller_symbol = $controller_symbol,
                e.qualified_name = $qualified_name,
                e.name = $name,
                e.start_line = $start_line,
                e.end_line = $end_line,
                e.framework = $framework,
                e.operation_id = $operation_id,
                e.request_schema = $request_schema,
                e.response_schema = $response_schema
            MERGE (f)-[:DEFINES]->(e)
            """
            try:
                self.client.execute_write(
                    ep_query,
                    {
                        "file_id": file_id,
                        "endpoint_id": ep.endpoint_id,
                        "repo_id": repo_id,
                        "file_path": ep.file_path,
                        "language": ep.language,
                        "http_method": ep.http_method,
                        "path": ep.path,
                        "controller_symbol": ep.controller_symbol,
                        "qualified_name": ep.qualified_name,
                        "name": f"{ep.http_method} {ep.path}",
                        "start_line": ep.start_line,
                        "end_line": ep.end_line,
                        "framework": ep.framework,
                        "operation_id": ep.operation_id or "",
                        "request_schema": ep.request_schema or "",
                        "response_schema": ep.response_schema or "",
                    },
                )
            except Exception as e:  # noqa: BLE001 # Partial graph ingestion fallback boundary
                logger.debug(f"Failed to ingest ApiEndpoint {ep.endpoint_id}: {e}")

        # 7. Create ApiClientCall nodes
        for call in data.api_client_calls:
            call_query = """
            MATCH (f:File {file_id: $file_id})
            MERGE (c:ApiClientCall {call_id: $call_id})
            SET c.repository_id = $repo_id,
                c.file_path = $file_path,
                c.language = $language,
                c.http_method = $http_method,
                c.url = $url,
                c.base_url = $base_url,
                c.client_symbol = $client_symbol,
                c.qualified_name = $client_symbol,
                c.name = $name,
                c.start_line = $start_line,
                c.end_line = $end_line
            MERGE (f)-[:DEFINES]->(c)
            """
            try:
                self.client.execute_write(
                    call_query,
                    {
                        "file_id": file_id,
                        "call_id": call.call_id,
                        "repo_id": repo_id,
                        "file_path": call.file_path,
                        "language": call.language,
                        "http_method": call.http_method,
                        "url": call.url,
                        "base_url": call.base_url,
                        "client_symbol": call.client_symbol,
                        "name": f"ClientCall {call.http_method} {call.url}",
                        "start_line": call.start_line,
                        "end_line": call.end_line,
                    },
                )
            except Exception as e:  # noqa: BLE001 # Partial graph ingestion fallback boundary
                logger.debug(f"Failed to ingest ApiClientCall {call.call_id}: {e}")

        # 8. Create ApiContract nodes
        for c in data.api_contracts:
            c_query = """
            MATCH (f:File {file_id: $file_id})
            MERGE (con:ApiContract {contract_id: $contract_id})
            SET con.repository_id = $repo_id,
                con.file_path = $file_path,
                con.operation_id = $operation_id,
                con.http_method = $http_method,
                con.path_template = $path_template,
                con.qualified_name = $qualified_name,
                con.name = $name,
                con.summary = $summary
            MERGE (f)-[:DEFINES]->(con)
            """
            try:
                self.client.execute_write(
                    c_query,
                    {
                        "file_id": file_id,
                        "contract_id": c.contract_id,
                        "repo_id": repo_id,
                        "file_path": c.file_path,
                        "operation_id": c.operation_id or "",
                        "http_method": c.http_method,
                        "path_template": c.path_template,
                        "qualified_name": f"Contract:{c.http_method}:{c.path_template}",
                        "name": f"Contract {c.http_method} {c.path_template}",
                        "summary": c.summary or "",
                    },
                )
            except Exception as e:  # noqa: BLE001 # Partial graph ingestion fallback boundary
                logger.debug(f"Failed to ingest ApiContract {c.contract_id}: {e}")

    def ingest_api_matches(self, matches: list) -> int:
        """Ingest matched cross-language API relationships into Neo4j graph."""
        count = 0
        for m in matches:
            source_id = getattr(m, "source_id", "")
            target_id = getattr(m, "target_id", "")
            match_reason = getattr(m, "match_reason", "")
            confidence_basis = getattr(m, "confidence_basis", "")
            file_path = getattr(m, "file_path", "")
            line_number = getattr(m, "line_number", 1)

            query = ""
            if match_reason == "IMPLEMENTS_CONTRACT":
                query = """
                MATCH (ep:ApiEndpoint {endpoint_id: $source_id})
                MATCH (c:ApiContract {contract_id: $target_id})
                MERGE (ep)-[r:IMPLEMENTS_CONTRACT]->(c)
                SET r.match_reason = $match_reason,
                    r.confidence_basis = $confidence_basis,
                    r.file_path = $file_path,
                    r.line_number = $line_number
                """
            elif match_reason == "MATCHES_CONTRACT":
                query = """
                MATCH (call:ApiClientCall {call_id: $source_id})
                MATCH (c:ApiContract {contract_id: $target_id})
                MERGE (call)-[r:MATCHES_CONTRACT]->(c)
                SET r.match_reason = $match_reason,
                    r.confidence_basis = $confidence_basis,
                    r.file_path = $file_path,
                    r.line_number = $line_number
                """
            else:
                # Default ClientCall -> ApiEndpoint
                query = """
                MATCH (call:ApiClientCall {call_id: $source_id})
                MATCH (ep:ApiEndpoint {endpoint_id: $target_id})
                MERGE (call)-[r:MATCHES_ENDPOINT]->(ep)
                SET r.match_reason = $match_reason,
                    r.confidence_basis = $confidence_basis,
                    r.file_path = $file_path,
                    r.line_number = $line_number
                """

            try:
                self.client.execute_write(
                    query,
                    {
                        "source_id": source_id,
                        "target_id": target_id,
                        "match_reason": match_reason,
                        "confidence_basis": confidence_basis,
                        "file_path": file_path,
                        "line_number": line_number,
                    },
                )
                count += 1
            except Exception as e:  # noqa: BLE001 # Partial graph ingestion fallback boundary
                logger.debug(f"Failed to write API match relationship {source_id} -> {target_id}: {e}")

        return count
