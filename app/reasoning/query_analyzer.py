"""Query Analyzer for classifying developer intent and extracting candidate terms."""

import re

from app.models.entities import QueryAnalysisResult
from app.utils.logger import logger


class QueryAnalyzer:
    """Analyzes natural language codebase queries to classify intent and extract target symbols."""

    def analyze(self, query: str, repository_id: str | None = None) -> QueryAnalysisResult:
        """Alias for analyze_query."""
        return self.analyze_query(query=query, repository_id=repository_id)

    def analyze_query(self, query: str, repository_id: str | None = None) -> QueryAnalysisResult:
        """Classify user question and extract candidate code symbols/file targets.

        Args:
            query: User natural language prompt.
            repository_id: Optional repository scope.

        Returns:
            QueryAnalysisResult object.
        """
        q_lower = query.lower()

        # Intent classification heuristics
        if any(w in q_lower for w in ["api contract", "openapi", "contract"]):
            intent = "api_contract"
        elif any(w in q_lower for w in ["fetch request", "frontend call", "client call", "api client"]):
            intent = "api_client"
        elif any(w in q_lower for w in ["backend endpoint", "endpoint", "controller implements", "handler"]):
            intent = "endpoint"
        elif any(
            w in q_lower
            for w in ["request flow", "api flow", "frontend to backend", "cross language", "cross-language"]
        ):
            intent = "api_flow"
        elif any(w in q_lower for w in ["who calls", "called by", "caller", "callers"]):
            intent = "callers"
        elif any(w in q_lower for w in ["what does", "calls", "callee", "callees", "functions called"]):
            intent = "callees"
        elif any(w in q_lower for w in ["depend on", "depends on", "dependencies", "dependents", "used by"]):
            intent = "dependency"
        elif any(w in q_lower for w in ["trace", "flow", "execution", "path from", "call path", "sequence"]):
            intent = "execution_flow"
        elif any(
            w in q_lower
            for w in ["diff", "what changed", "changed between", "last commit", "commit changes", "symbol changed"]
        ):
            intent = "diff"
        elif any(w in q_lower for w in ["affected", "impact", "change", "modifying"]):
            intent = "impact"
        elif any(w in q_lower for w in ["architecture", "structure", "overview", "design"]):
            intent = "architecture"
        elif any(w in q_lower for w in ["where is", "find symbol", "defined", "definition"]):
            intent = "symbol_lookup"
        else:
            intent = "general_code_question"

        # Repository identification from query context if not explicitly provided
        detected_repo = repository_id
        if not detected_repo:
            repo_match = re.search(r"\bin\s+([a-zA-Z0-9_\-]+)\b", query, re.IGNORECASE)
            if repo_match:
                detected_repo = repo_match.group(1).lower()
            elif "aegisops" in q_lower:
                detected_repo = "aegisops"

        # Candidate symbol & file extraction heuristics
        # 1. Look for CamelCase or snake_case terms or terms with parentheses/dots
        symbol_pattern = r"\b[A-Z][a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)*\b|\b[a-z_][a-z0-9_]*(?:\.[a-z0-9_]+)+\b|\b[a-z0-9_]+_[a-z0-9_]+\b"
        raw_symbols = re.findall(symbol_pattern, query)

        # 2. Extract API URL paths e.g. /api/users, GET /api/users, /users
        api_path_pattern = r"((?:(?:GET|POST|PUT|DELETE|PATCH)\s+)?/[a-zA-Z0-9_\-/{}\:]+)"
        api_paths = re.findall(api_path_pattern, query, re.IGNORECASE)

        # 3. Look for file extensions (.py, .js, etc.)
        file_pattern = r"\b[a-zA-Z0-9_\-/]+\.(?:py|js|ts|java|go|yaml|yml|json|md)\b"
        candidate_files = re.findall(file_pattern, query)

        # English instruction words and query keywords to exclude from candidate code symbols
        stop_symbols = {
            "trace",
            "explain",
            "present",
            "highlight",
            "identify",
            "describe",
            "show",
            "do",
            "not",
            "the",
            "this",
            "that",
            "http",
            "https",
            "api",
            "rest",
            "postgresql",
            "postgres",
            "mysql",
            "database",
            "get",
            "post",
            "put",
            "delete",
            "patch",
            "aegisops",
            "step",
            "flow",
            "actual",
            "source",
            "class",
            "classes",
            "function",
            "functions",
            "relationship",
            "relationships",
            "evidence",
            "middleware",
            "dependency",
            "dependencies",
            "background",
            "task",
            "tasks",
        }

        # Clean candidate symbols
        cleaned_symbols = []
        for p in api_paths:
            p_clean = p.strip()
            if p_clean and p_clean not in cleaned_symbols:
                cleaned_symbols.append(p_clean)
                # If it had a method prefix, also include bare path
                parts = p_clean.split()
                if len(parts) == 2 and parts[1] not in cleaned_symbols:
                    cleaned_symbols.append(parts[1])

        for s in raw_symbols:
            clean_s = s.strip("?,.()")
            if clean_s and len(clean_s) > 2 and clean_s.lower() not in stop_symbols and clean_s not in cleaned_symbols:
                cleaned_symbols.append(clean_s)

        # Determine requested hops
        requested_hops = 2
        if "3" in query or "deep" in query or "transitive" in query:
            requested_hops = 3
        elif "1" in query or "direct" in query:
            requested_hops = 1

        result = QueryAnalysisResult(
            query=query,
            intent=intent,
            candidate_symbols=cleaned_symbols,
            candidate_files=candidate_files,
            requested_hops=requested_hops,
            repository_id=detected_repo,
        )

        logger.info(f"[QueryAnalyzer] Intent: '{intent}', Candidates: {cleaned_symbols}, Files: {candidate_files}")
        return result
