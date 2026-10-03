"""Static API endpoint, client call, and OpenAPI contract extractor."""

import json
import re
from pathlib import Path
from typing import Any
import yaml

from app.models.entities import (
    ApiClientCall,
    ApiContract,
    ApiEndpoint,
    SourceFile,
)
from app.parsing.tree_sitter_base import generate_symbol_id
from app.parsing.url_normalizer import normalize_http_method, normalize_url_path
from app.utils.logger import logger


class APIExtractor:
    """Extracts static API endpoints, client calls, and OpenAPI contracts from codebase files."""

    # Python FastAPI / Flask route patterns
    PYTHON_ROUTE_REGEX = re.compile(
        r"@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    )
    PYTHON_FLASK_ROUTE_REGEX = re.compile(
        r"@app\.route\s*\(\s*['\"]([^'\"]+)['\"](?:.*?methods\s*=\s*\[\s*['\"]([^'\"]+)['\"]\s*\])?",
        re.IGNORECASE,
    )

    # Java Spring route patterns
    JAVA_SPRING_ROUTE_REGEX = re.compile(
        r"@(Get|Post|Put|Delete|Patch|Request)Mapping\s*\(\s*(?:value\s*=\s*)?['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    )

    # Go HTTP router patterns
    GO_HTTP_ROUTE_REGEX = re.compile(
        r"(?:http\.HandleFunc|r\.(?:GET|POST|PUT|DELETE|Handle))\s*\(\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    )

    # JS/TS fetch & axios patterns
    JS_FETCH_REGEX = re.compile(
        r"fetch\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*\{\s*method\s*:\s*['\"]([^'\"]+)['\"])?",
        re.IGNORECASE,
    )
    JS_AXIOS_METHOD_REGEX = re.compile(
        r"axios\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    )
    JS_AXIOS_CONFIG_REGEX = re.compile(
        r"axios\s*\(\s*\{[^}]*url\s*:\s*['\"]([^'\"]+)['\"](?:[^}]*method\s*:\s*['\"]([^'\"]+)['\"])?",
        re.IGNORECASE | re.DOTALL,
    )

    def extract_from_content(
        self,
        source_file: SourceFile,
        content: str,
        repository_id: str,
    ) -> tuple[list[ApiEndpoint], list[ApiClientCall], list[ApiContract]]:
        """Extract API endpoints, client calls, or contracts from file content."""
        endpoints: list[ApiEndpoint] = []
        client_calls: list[ApiClientCall] = []
        contracts: list[ApiContract] = []

        file_path = source_file.relative_path.replace("\\", "/")
        ext = source_file.extension.lower()
        filename = Path(file_path).name.lower()

        # 1. Check OpenAPI / Swagger spec files
        if filename in ("openapi.yaml", "openapi.yml", "openapi.json", "swagger.json", "swagger.yaml") or ext in (".yaml", ".yml"):
            try:
                parsed_contracts = self._extract_openapi_contracts(file_path, content, repository_id)
                if parsed_contracts:
                    for c in parsed_contracts:
                        logger.info(f"[openapi_contract_detected] Contract {c.http_method} {c.path_template} in {c.file_path}")
                    contracts.extend(parsed_contracts)
                    return endpoints, client_calls, contracts
            except Exception as e:
                logger.debug(f"File {file_path} is not an OpenAPI spec: {e}")

        lines = content.splitlines()

        # 2. Extract Backend Routes by language
        if source_file.language == "python":
            endpoints.extend(self._extract_python_endpoints(file_path, lines, repository_id))
        elif source_file.language == "java":
            endpoints.extend(self._extract_java_endpoints(file_path, lines, repository_id))
        elif source_file.language == "go":
            endpoints.extend(self._extract_go_endpoints(file_path, lines, repository_id))

        for ep in endpoints:
            logger.info(f"[api_endpoint_detected] Endpoint {ep.http_method} {ep.path} in {ep.file_path}:{ep.start_line}")

        # 3. Extract Frontend / Client API calls (JS, TS, Python, etc.)
        if source_file.language in ("javascript", "typescript", "python"):
            extracted_calls = self._extract_client_calls(file_path, source_file.language, lines, repository_id)
            for call in extracted_calls:
                logger.info(f"[api_client_call_detected] Client call {call.http_method} {call.url} in {call.file_path}:{call.start_line}")
            client_calls.extend(extracted_calls)

        return endpoints, client_calls, contracts

    def _extract_python_endpoints(self, file_path: str, lines: list[str], repository_id: str) -> list[ApiEndpoint]:
        endpoints: list[ApiEndpoint] = []
        mod_name = file_path.removesuffix(".py").replace("/", ".")

        for line_idx, line in enumerate(lines, 1):
            # FastAPI style
            for match in self.PYTHON_ROUTE_REGEX.finditer(line):
                method = normalize_http_method(match.group(1))
                path = normalize_url_path(match.group(2))

                # Look ahead for def function_name
                handler_symbol = f"{mod_name}.route_l{line_idx}"
                for next_line in lines[line_idx : line_idx + 5]:
                    fn_match = re.search(r"def\s+([a-zA-Z0-9_]+)", next_line)
                    if fn_match:
                        handler_symbol = f"{mod_name}.{fn_match.group(1)}"
                        break

                qn = f"{method}:{path}"
                eid = generate_symbol_id(repository_id, file_path, qn)
                endpoints.append(
                    ApiEndpoint(
                        endpoint_id=eid,
                        repository_id=repository_id,
                        file_path=file_path,
                        language="python",
                        http_method=method,
                        path=path,
                        controller_symbol=handler_symbol,
                        qualified_name=qn,
                        start_line=line_idx,
                        end_line=line_idx + 10,
                        framework="FastAPI",
                    )
                )

            # Flask style
            for match in self.PYTHON_FLASK_ROUTE_REGEX.finditer(line):
                path = normalize_url_path(match.group(1))
                method = normalize_http_method(match.group(2)) if match.group(2) else "GET"
                qn = f"{method}:{path}"
                eid = generate_symbol_id(repository_id, file_path, qn)
                endpoints.append(
                    ApiEndpoint(
                        endpoint_id=eid,
                        repository_id=repository_id,
                        file_path=file_path,
                        language="python",
                        http_method=method,
                        path=path,
                        controller_symbol=f"{mod_name}.route_l{line_idx}",
                        qualified_name=qn,
                        start_line=line_idx,
                        end_line=line_idx + 10,
                        framework="Flask",
                    )
                )

        return endpoints

    def _extract_java_endpoints(self, file_path: str, lines: list[str], repository_id: str) -> list[ApiEndpoint]:
        endpoints: list[ApiEndpoint] = []
        pkg_name = file_path.removesuffix(".java").replace("/", ".")

        for line_idx, line in enumerate(lines, 1):
            for match in self.JAVA_SPRING_ROUTE_REGEX.finditer(line):
                mapping_type = match.group(1).upper()
                raw_path = match.group(2)
                path = normalize_url_path(raw_path)

                if "GET" in mapping_type:
                    method = "GET"
                elif "POST" in mapping_type:
                    method = "POST"
                elif "PUT" in mapping_type:
                    method = "PUT"
                elif "DELETE" in mapping_type:
                    method = "DELETE"
                else:
                    method = "GET"

                handler_symbol = f"{pkg_name}.endpoint_l{line_idx}"
                for next_line in lines[line_idx : line_idx + 5]:
                    fn_match = re.search(r"public\s+[\w<>]+\s+([a-zA-Z0-9_]+)\s*\(", next_line)
                    if fn_match:
                        handler_symbol = f"{pkg_name}.{fn_match.group(1)}"
                        break

                qn = f"{method}:{path}"
                eid = generate_symbol_id(repository_id, file_path, qn)
                endpoints.append(
                    ApiEndpoint(
                        endpoint_id=eid,
                        repository_id=repository_id,
                        file_path=file_path,
                        language="java",
                        http_method=method,
                        path=path,
                        controller_symbol=handler_symbol,
                        qualified_name=qn,
                        start_line=line_idx,
                        end_line=line_idx + 15,
                        framework="Spring",
                    )
                )

        return endpoints

    def _extract_go_endpoints(self, file_path: str, lines: list[str], repository_id: str) -> list[ApiEndpoint]:
        endpoints: list[ApiEndpoint] = []
        pkg_name = file_path.removesuffix(".go").replace("/", ".")

        for line_idx, line in enumerate(lines, 1):
            for match in self.GO_HTTP_ROUTE_REGEX.finditer(line):
                raw_path = match.group(1)
                path = normalize_url_path(raw_path)
                method = "GET"
                if "POST" in line.upper():
                    method = "POST"

                qn = f"{method}:{path}"
                eid = generate_symbol_id(repository_id, file_path, qn)
                endpoints.append(
                    ApiEndpoint(
                        endpoint_id=eid,
                        repository_id=repository_id,
                        file_path=file_path,
                        language="go",
                        http_method=method,
                        path=path,
                        controller_symbol=f"{pkg_name}.handle_l{line_idx}",
                        qualified_name=qn,
                        start_line=line_idx,
                        end_line=line_idx + 10,
                        framework="net/http",
                    )
                )

        return endpoints

    def _extract_client_calls(self, file_path: str, language: str, lines: list[str], repository_id: str) -> list[ApiClientCall]:
        calls: list[ApiClientCall] = []
        mod_name = file_path.replace("/", ".")

        for line_idx, line in enumerate(lines, 1):
            # 1. Fetch
            for match in self.JS_FETCH_REGEX.finditer(line):
                raw_url = match.group(1)
                raw_method = match.group(2) or "GET"
                url = normalize_url_path(raw_url)
                method = normalize_http_method(raw_method)
                cid = generate_symbol_id(repository_id, file_path, f"client:{method}:{url}:{line_idx}")

                calls.append(
                    ApiClientCall(
                        call_id=cid,
                        repository_id=repository_id,
                        file_path=file_path,
                        language=language,
                        http_method=method,
                        url=url,
                        client_symbol=f"{mod_name}.fetch_l{line_idx}",
                        start_line=line_idx,
                        end_line=line_idx,
                    )
                )

            # 2. Axios method e.g. axios.get('/api/users')
            for match in self.JS_AXIOS_METHOD_REGEX.finditer(line):
                method = normalize_http_method(match.group(1))
                raw_url = match.group(2)
                url = normalize_url_path(raw_url)
                cid = generate_symbol_id(repository_id, file_path, f"axios:{method}:{url}:{line_idx}")

                calls.append(
                    ApiClientCall(
                        call_id=cid,
                        repository_id=repository_id,
                        file_path=file_path,
                        language=language,
                        http_method=method,
                        url=url,
                        client_symbol=f"{mod_name}.axios_l{line_idx}",
                        start_line=line_idx,
                        end_line=line_idx,
                    )
                )

        return calls

    def _extract_openapi_contracts(self, file_path: str, content: str, repository_id: str) -> list[ApiContract]:
        contracts: list[ApiContract] = []
        try:
            if file_path.endswith(".json"):
                data = json.loads(content)
            else:
                data = yaml.safe_load(content)
        except Exception:
            return contracts

        if not isinstance(data, dict) or "paths" not in data:
            return contracts

        paths_dict = data.get("paths", {})
        for path_pattern, path_item in paths_dict.items():
            if not isinstance(path_item, dict):
                continue

            for method_key, op_data in path_item.items():
                if method_key.lower() not in ("get", "post", "put", "delete", "patch", "head", "options"):
                    continue
                if not isinstance(op_data, dict):
                    continue

                method = normalize_http_method(method_key)
                norm_path = normalize_url_path(path_pattern)
                op_id = op_data.get("operationId")
                summary = op_data.get("summary")
                cid = generate_symbol_id(repository_id, file_path, f"contract:{method}:{norm_path}")

                contracts.append(
                    ApiContract(
                        contract_id=cid,
                        repository_id=repository_id,
                        file_path=file_path,
                        operation_id=op_id,
                        http_method=method,
                        path_template=norm_path,
                        summary=summary,
                        schemas=op_data.get("responses", {}),
                    )
                )

        return contracts
