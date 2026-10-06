"""Tree-sitter base parser implementation for multi-language AST extraction."""

import uuid
from abc import abstractmethod
from typing import Any

from tree_sitter_languages import get_parser

from app.models.entities import (
    CallRelation,
    CodeChunk,
    CodeSymbol,
    ExtractedCodeData,
    ImportInfo,
    InheritanceRelation,
    SourceFile,
)
from app.parsing.base import BaseParser
from app.utils.exceptions import ParserError
from app.utils.logger import logger


def generate_symbol_id(repo_id: str, file_path: str, qualified_name: str) -> str:
    """Generate deterministic UUID string for code entities."""
    clean_path = file_path.replace("\\", "/")
    raw = f"{repo_id}:{clean_path}:{qualified_name}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))


def generate_chunk_id(repo_id: str, file_path: str, start_line: int, end_line: int, symbol_name: str = "") -> str:
    """Generate deterministic UUID string for code chunks."""
    clean_path = file_path.replace("\\", "/")
    raw = f"{repo_id}:{clean_path}:{start_line}:{end_line}:{symbol_name}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))


class TreeSitterBaseParser(BaseParser):
    """Abstract base class for Tree-sitter powered language parsers."""

    def __init__(self, language: str, ts_language_name: str | None = None):
        self.language = language.lower()
        self.ts_language_name = (ts_language_name or self.language).lower()
        self._ts_parser = None

    def _get_ts_parser(self):
        if self._ts_parser is None:
            try:
                import warnings

                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=FutureWarning, module="tree_sitter")
                    warnings.filterwarnings("ignore", category=FutureWarning, message=".*Language.*is deprecated.*")
                    self._ts_parser = get_parser(self.ts_language_name)
            except Exception as e:  # noqa: BLE001 — Tree-sitter parser initialization boundary
                raise ParserError(f"Failed to initialize tree-sitter parser for '{self.ts_language_name}': {e}")
        return self._ts_parser

    def parse_file(self, source_file: SourceFile, content: str, repository_id: str) -> ExtractedCodeData:
        """Parse source file using tree-sitter and extract structured data."""
        clean_rel_path = source_file.relative_path.replace("\\", "/")
        try:
            ts_parser = self._get_ts_parser()
            content_bytes = bytes(content, "utf-8")
            tree = ts_parser.parse(content_bytes)
        except Exception as e:  # noqa: BLE001 — Fallback for malformed source code parsing failures
            logger.warning(f"Error parsing {clean_rel_path} with Tree-sitter ({self.language}): {e}")
            return ExtractedCodeData(repository_id=repository_id, file_info=source_file)

        symbols: list[CodeSymbol] = []
        imports: list[ImportInfo] = []
        calls: list[CallRelation] = []
        inheritance: list[InheritanceRelation] = []

        try:
            self._extract_ast_data(
                tree.root_node,
                content_bytes,
                content,
                clean_rel_path,
                repository_id,
                symbols,
                imports,
                calls,
                inheritance,
            )
        except Exception as e:  # noqa: BLE001 — AST traversal boundary for malformed code nodes
            logger.warning(f"Failed during tree-sitter traversal for {clean_rel_path}: {e}")

        # Generate symbol-aware chunks
        chunks = self._create_chunks(content, symbols, clean_rel_path, repository_id)

        return ExtractedCodeData(
            repository_id=repository_id,
            file_info=source_file,
            symbols=symbols,
            imports=imports,
            calls=calls,
            inheritance=inheritance,
            chunks=chunks,
        )

    @abstractmethod
    def _extract_ast_data(
        self,
        root_node: Any,
        content_bytes: bytes,
        content_str: str,
        file_path: str,
        repository_id: str,
        symbols: list[CodeSymbol],
        imports: list[ImportInfo],
        calls: list[CallRelation],
        inheritance: list[InheritanceRelation],
    ):
        """Language-specific AST extraction implementation."""

    def _node_text(self, node: Any, content_bytes: bytes) -> str:
        """Extract UTF-8 decoded text from a tree-sitter node."""
        if not node:
            return ""
        return content_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

    def _line_range(self, node: Any) -> tuple[int, int]:
        """Return 1-indexed (start_line, end_line) line range for node."""
        start = node.start_point[0] + 1
        end = node.end_point[0] + 1
        return start, end

    def _create_chunks(
        self,
        content: str,
        symbols: list[CodeSymbol],
        file_path: str,
        repository_id: str,
    ) -> list[CodeChunk]:
        """Create code chunks based on extracted symbol line ranges or file blocks."""
        chunks: list[CodeChunk] = []
        lines = content.splitlines()
        total_lines = len(lines)

        if not symbols:
            if total_lines > 0:
                cid = generate_chunk_id(repository_id, file_path, 1, total_lines)
                chunks.append(
                    CodeChunk(
                        chunk_id=cid,
                        repository_id=repository_id,
                        file_path=file_path,
                        language=self.language,
                        symbol_name=None,
                        symbol_type=None,
                        start_line=1,
                        end_line=total_lines,
                        content=content,
                    )
                )
            return chunks

        for sym in symbols:
            st = max(1, sym.start_line)
            end = min(total_lines, sym.end_line)
            if st <= end:
                snippet = "\n".join(lines[st - 1 : end])
                cid = generate_chunk_id(repository_id, file_path, st, end, sym.symbol_name)
                chunks.append(
                    CodeChunk(
                        chunk_id=cid,
                        repository_id=repository_id,
                        file_path=file_path,
                        language=self.language,
                        symbol_name=sym.symbol_name,
                        symbol_type=sym.symbol_type.value
                        if hasattr(sym.symbol_type, "value")
                        else str(sym.symbol_type),
                        start_line=st,
                        end_line=end,
                        content=snippet,
                        parent_symbol=sym.parent_symbol,
                    )
                )

        return chunks
