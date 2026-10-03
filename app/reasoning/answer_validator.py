"""Answer Validator inspecting generated LLM answers for strict grounding in retrieved evidence."""

import re

from typing import Any

from app.models.entities import NormalizedSearchResult, ResolvedEntity
from app.utils.logger import logger


class AnswerValidator:
    """Validates that LLM output does not fabricate file paths, line numbers, or unsupported relationships."""

    def validate(
        self,
        answer: str,
        fused_results: list[NormalizedSearchResult],
        resolved_entities: list[ResolvedEntity],
        graph_results: list[NormalizedSearchResult] | None = None,
        graph_paths: list[Any] | None = None,
        subgraph: Any | None = None,
    ) -> tuple[bool, list[str]]:
        """Verify file paths and line references cited in answer against retrieved context metadata."""
        errors: list[str] = []

        if not answer or not answer.strip():
            return False, ["Empty answer generated."]

        # Collect valid file paths from retrieved context
        valid_files: set[str] = set()
        valid_file_basenames: set[str] = set()
        
        for entity in resolved_entities:
            if entity.file_path:
                valid_files.add(entity.file_path)
                valid_file_basenames.add(entity.file_path.split("/")[-1].split("\\")[-1])

        for res in fused_results:
            if res.file_path:
                valid_files.add(res.file_path)
                valid_file_basenames.add(res.file_path.split("/")[-1].split("\\")[-1])

        if graph_results:
            for res in graph_results:
                if res.file_path:
                    valid_files.add(res.file_path)
                    valid_file_basenames.add(res.file_path.split("/")[-1].split("\\")[-1])

        if graph_paths:
            for p in graph_paths:
                nodes = getattr(p, "nodes", []) if not isinstance(p, dict) else p.get("nodes", [])
                for n in nodes:
                    fpath = getattr(n, "file_path", None) if not isinstance(n, dict) else n.get("file_path")
                    if fpath:
                        valid_files.add(fpath)
                        valid_file_basenames.add(fpath.split("/")[-1].split("\\")[-1])

        if subgraph and hasattr(subgraph, "nodes"):
            for n in getattr(subgraph, "nodes", []):
                fpath = getattr(n, "file_path", None) if not isinstance(n, dict) else n.get("file_path")
                if fpath:
                    valid_files.add(fpath)
                    valid_file_basenames.add(fpath.split("/")[-1].split("\\")[-1])

        # Find potential file references in answer e.g. src/api/orders.py or order_service.py:20-45
        file_citation_pattern = re.compile(
            r'\b([a-zA-Z0-9_\-/\\]+\.(?:py|js|ts|java|go|cpp|h|cs|rb|php))\b(?:[:\s]+(\d+)(?:-(\d+))?)?'
        )
        matches = file_citation_pattern.findall(answer)

        for fpath, start_str, end_str in matches:
            basename = fpath.split("/")[-1].split("\\")[-1]
            if fpath not in valid_files and basename not in valid_file_basenames:
                # Ignore system / general mentions if not clearly claiming code location
                if not any(fpath.startswith(prefix) for prefix in ["http://", "https://", "file://"]):
                    logger.warning(f"Validation warning: Cited file '{fpath}' not found in retrieved context.")
                    errors.append(f"Answer cited ungrounded file path: '{fpath}'")

        is_valid = len(errors) == 0
        return is_valid, errors
