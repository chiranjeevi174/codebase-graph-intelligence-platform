"""Deterministic Mock LLM Provider for offline testing and CI workflows."""

from __future__ import annotations

import re
from typing import Any

from app.llm.base import BaseLLMProvider
from app.utils.logger import logger


class MockLLMProvider(BaseLLMProvider):
    """Deterministic, provider-agnostic mock LLM producing grounded responses from retrieved context."""

    def __init__(self, settings: Any = None, **kwargs: Any) -> None:
        super().__init__(settings=settings, **kwargs)
        self._model = "mock-deterministic-v1"

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """Synchronously generate a deterministic, evidence-grounded structured response."""
        return self._generate_response(prompt)

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """Asynchronously generate a deterministic, evidence-grounded structured response."""
        return self._generate_response(prompt)

    def _generate_response(self, prompt: str) -> str:
        # Extract user question
        q_match = re.search(r"User Question:\s*(.*?)(?=\n\nRetrieved Codebase Evidence|\Z)", prompt, re.DOTALL)
        question = q_match.group(1).strip() if q_match else "Codebase Query"

        # Extract retrieved context
        ctx_match = re.search(r"Retrieved Codebase Evidence & Graph Context:\s*(.*)", prompt, re.DOTALL)
        context = ctx_match.group(1).strip() if ctx_match else prompt

        # 1. Extract verified file paths with line ranges strictly from context
        file_lines: list[tuple[str, int, int]] = []
        for m in re.finditer(
            r"(?:File:\s*|in\s*`)([a-zA-Z0-9_\-/\\]+\.(?:py|js|ts|java|go|cpp|h|cs|rb|php)):(\d+)(?:-(\d+))?",
            context,
        ):
            fpath = m.group(1).replace("\\", "/")
            start_l = int(m.group(2))
            end_l = int(m.group(3)) if m.group(3) else start_l
            file_lines.append((fpath, start_l, end_l))

        for m in re.finditer(
            r"### File:\s*([a-zA-Z0-9_\-/\\]+\.(?:py|js|ts|java|go|cpp|h|cs|rb|php))\s*\(Lines\s*(\d+)-(\d+)\)",
            context,
        ):
            fpath = m.group(1).replace("\\", "/")
            file_lines.append((fpath, int(m.group(2)), int(m.group(3))))

        # Deduplicate preserving order
        seen_files: set[str] = set()
        unique_citations: list[tuple[str, int, int]] = []
        for fp, s, e in file_lines:
            if fp not in seen_files:
                seen_files.add(fp)
                unique_citations.append((fp, s, e))

        # 2. Extract verified symbols strictly from context
        symbols: list[str] = []
        for m in re.finditer(r"Symbol:\s*([a-zA-Z0-9_.]+)", context):
            sym = m.group(1).strip()
            if sym not in ("N/A", "") and sym not in symbols:
                symbols.append(sym)
        for m in re.finditer(r"-\s*([a-zA-Z0-9_]+)\s*\([A-Za-z]+\)\s*->\s*`([a-zA-Z0-9_.]+)`", context):
            sym = m.group(2).strip()
            if sym not in symbols:
                symbols.append(sym)

        # 3. Extract verified graph paths / flows strictly from context
        graph_paths = [m.group(1).strip() for m in re.finditer(r"-\s*\[\d+\s*hops\]\s*(.+)", context)]
        api_flows = [m.group(1).strip() for m in re.finditer(r"API Flow Path:\s*(.+)", context)]
        graph_edges = [
            m.group(0).strip().removeprefix("- ").strip()
            for m in re.finditer(r"-\s*`[^`]+`\s*-\[[^\]]+\]->\s*`[^`]+`", context)
        ]

        # 4. Formulate evidence-grounded answer sections
        if unique_citations:
            citations_md = "\n".join([f"- `{fp}:{s}-{e}`" for fp, s, e in unique_citations[:6]])
            primary_file = unique_citations[0][0]
            primary_evidence_text = f"`{primary_file}`"
        else:
            citations_md = "No file-level evidence was extracted from the retrieved context."
            primary_evidence_text = "the retrieved context"

        if symbols:
            top_symbols = ", ".join([f"`{s}`" for s in symbols[:3]])
            direct_answer = (
                f"Based on the verified evidence from {primary_evidence_text}, the query relates to {top_symbols}."
            )
        elif unique_citations:
            direct_answer = (
                f"Based on the verified evidence in {primary_evidence_text}, relevant definitions were identified."
            )
        else:
            direct_answer = "Based on the retrieved context, no verifiable file or symbol evidence was identified."

        explanation_points: list[str] = []
        if unique_citations:
            explanation_points.append(
                "Retrieved code evidence identifies definitions across verified files: "
                + ", ".join([f"`{fp}`" for fp, _, _ in unique_citations[:3]])
                + "."
            )
        else:
            explanation_points.append("No file-level evidence was retrieved for analysis.")

        if symbols:
            explanation_points.append(
                "Identified symbols in context: " + ", ".join([f"`{s}`" for s in symbols[:4]]) + "."
            )

        if graph_paths:
            path_strs = "; ".join([f"`{p}`" for p in graph_paths[:3]])
            explanation_points.append(f"Verified graph paths: {path_strs}.")
        elif api_flows:
            flow_strs = "; ".join([f"`{p}`" for p in api_flows[:3]])
            explanation_points.append(f"Verified API execution flow: {flow_strs}.")
        elif graph_edges:
            edge_strs = "; ".join([f"`{e}`" for e in graph_edges[:3]])
            explanation_points.append(f"Verified graph relationships: {edge_strs}.")
        else:
            explanation_points.append("No multi-hop graph traversal paths were present in the retrieved context.")

        explanation_body = "\n".join([f"- {pt}" for pt in explanation_points])

        # Architectural impact: only describe when retrieved context explicitly provides supporting evidence
        arch_match = re.search(r"(?:###\s*)?Architectural Impact:\s*(.+)", context, re.IGNORECASE)
        if arch_match:
            impact_text = arch_match.group(1).strip()
        elif graph_paths:
            impact_text = (
                "The retrieved graph paths substantiate structural dependencies: "
                + "; ".join([f"`{p}`" for p in graph_paths[:2]])
                + "."
            )
        elif api_flows:
            impact_text = (
                "The retrieved API flow demonstrates integration across components: "
                + "; ".join([f"`{p}`" for p in api_flows[:2]])
                + "."
            )
        elif graph_edges:
            impact_text = (
                "The retrieved graph relationships substantiate direct component coupling: "
                + "; ".join([f"{e}" for e in graph_edges[:2]])
                + "."
            )
        else:
            impact_text = "Architectural impact cannot be established from the retrieved evidence."

        if unique_citations:
            next_steps = (
                "Review the referenced implementations in "
                + ", ".join([f"`{fp}`" for fp, _, _ in unique_citations[:3]])
                + " to verify interface contracts and error handling."
            )
        else:
            next_steps = "Ensure the repository is indexed into the graph and vector stores before repeating the query."

        answer = f"""### Direct Answer
{direct_answer}

### Explanation
{explanation_body}

### Relevant Files & Symbols
{citations_md}

### Why It Matters & Architectural Impact
{impact_text}

### Developer Next Steps
{next_steps}
"""
        logger.info(
            f"[MockLLMProvider] Generated grounded mock response for '{question[:40]}...' ({len(answer)} chars)."
        )
        return answer
