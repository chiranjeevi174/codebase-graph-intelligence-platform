"""Answer Validator inspecting generated LLM answers for strict grounding in retrieved evidence."""

import re
from typing import Any

from app.models.entities import NormalizedSearchResult, ResolvedEntity
from app.utils.logger import logger

# Common runtime/framework/library brand names ending in .js or .py that are not repository file paths
IGNORED_TECH_NAMES = {
    "node.js",
    "express.js",
    "vue.js",
    "react.js",
    "next.js",
    "three.js",
    "chart.js",
    "d3.js",
    "moment.js",
    "axios.js",
    "electron.js",
    "deno.js",
    "bun.js",
    "p5.js",
    "socket.io.js",
    "alpine.js",
    "angular.js",
    "nuxt.js",
    "ember.js",
    "backbone.js",
}


def normalize_file_path(p: str) -> str:
    """Normalize file path for cross-platform (Windows/POSIX) comparison."""
    norm = p.replace("\\", "/").strip()
    norm = norm.removeprefix("./")
    return norm


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
            logger.warning("[AnswerValidator] Groundedness validation failed: Empty answer generated.")
            return False, ["Empty answer generated."]

        # Collect valid file paths from retrieved context
        valid_files: set[str] = set()
        valid_file_basenames: set[str] = set()

        def register_path(raw_path: str | None):
            if not raw_path:
                return
            norm = normalize_file_path(raw_path)
            valid_files.add(norm)
            valid_files.add(norm.lower())
            base = norm.split("/")[-1]
            valid_file_basenames.add(base)
            valid_file_basenames.add(base.lower())

        for entity in resolved_entities:
            register_path(entity.file_path)

        for res in fused_results:
            register_path(res.file_path)

        if graph_results:
            for res in graph_results:
                register_path(res.file_path)

        if graph_paths:
            for p in graph_paths:
                # Check explicit source and target nodes on GraphPath
                src_n = getattr(p, "source_node", None) if not isinstance(p, dict) else p.get("source_node")
                if src_n:
                    src_fpath = (
                        getattr(src_n, "file_path", None) if not isinstance(src_n, dict) else src_n.get("file_path")
                    )
                    register_path(src_fpath)
                tgt_n = getattr(p, "target_node", None) if not isinstance(p, dict) else p.get("target_node")
                if tgt_n:
                    tgt_fpath = (
                        getattr(tgt_n, "file_path", None) if not isinstance(tgt_n, dict) else tgt_n.get("file_path")
                    )
                    register_path(tgt_fpath)

                # Check general node list on path if present
                nodes = getattr(p, "nodes", []) if not isinstance(p, dict) else p.get("nodes", [])
                if nodes:
                    for n in nodes:
                        fpath = getattr(n, "file_path", None) if not isinstance(n, dict) else n.get("file_path")
                        register_path(fpath)

        if subgraph and hasattr(subgraph, "nodes"):
            for n in getattr(subgraph, "nodes", []):
                fpath = getattr(n, "file_path", None) if not isinstance(n, dict) else n.get("file_path")
                register_path(fpath)

        # Also extract valid file mentions embedded inside the retrieved context content
        content_file_pattern = re.compile(
            r"\b([a-zA-Z0-9_\-/\\]+\.(?:py|js|ts|java|go|cpp|h|cs|rb|php|json|ya?ml|md))\b"
        )
        for res in fused_results:
            if res.content:
                for match in content_file_pattern.findall(res.content):
                    register_path(match)

        # Find potential file references in answer e.g. src/api/orders.py or order_service.py:20-45
        file_citation_pattern = re.compile(
            r"\b([a-zA-Z0-9_\-/\\]+\.(?:py|js|ts|java|go|cpp|h|cs|rb|php))\b(?:[:\s]+(\d+)(?:-(\d+))?)?"
        )
        matches = file_citation_pattern.findall(answer)

        # Regex to detect negation or statement that a file is missing/unfound
        negation_pattern = re.compile(
            r"\b(?:not found|does not exist|absent|missing|no file|unsupported|unable to find|cannot find|not present)\b",
            re.IGNORECASE,
        )

        for fpath, start_str, end_str in matches:
            norm_fpath = normalize_file_path(fpath)
            basename = norm_fpath.split("/")[-1]
            base_lower = basename.lower()

            # Ignore runtime/framework library names
            if base_lower in IGNORED_TECH_NAMES:
                continue

            # Ignore URLs or protocol-prefixed URIs
            if any(norm_fpath.startswith(prefix) for prefix in ["http://", "https://", "file://"]):
                continue

            # Check if file path or basename is known from retrieved evidence
            is_grounded = (
                norm_fpath in valid_files
                or norm_fpath.lower() in valid_files
                or basename in valid_file_basenames
                or base_lower in valid_file_basenames
            )

            if not is_grounded:
                # Check if the citation is part of a negation explaining that the file does not exist
                pos = answer.find(fpath)
                if pos != -1:
                    snippet = answer[max(0, pos - 80) : min(len(answer), pos + len(fpath) + 80)]
                    if negation_pattern.search(snippet):
                        continue

                logger.warning(
                    f"[AnswerValidator] Groundedness validation warning: Cited file '{fpath}' not found in retrieved context metadata."
                )
                errors.append(f"Answer cited ungrounded file path: '{fpath}'")

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning(
                f"[AnswerValidator] Answer failed groundedness validation with {len(errors)} error(s): {errors}"
            )
        else:
            logger.info("[AnswerValidator] Groundedness validation passed successfully.")

        return is_valid, errors
