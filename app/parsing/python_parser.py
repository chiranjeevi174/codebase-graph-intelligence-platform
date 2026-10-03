"""Python AST code parser implementation using built-in ast module."""

import ast
import uuid
from collections.abc import Sequence

from app.models.entities import (
    ClassInfo,
    CodeChunk,
    CodeSymbol,
    ExtractedCodeData,
    FunctionInfo,
    MethodInfo,
    SourceFile,
    SymbolType,
)
from app.parsing.base import BaseParser
from app.parsing.relationship_extractor import ASTRelationshipVisitor
from app.utils.exceptions import ParserError
from app.utils.logger import logger


def generate_symbol_id(repo_id: str, file_path: str, qualified_name: str) -> str:
    """Generate deterministic UUID string for code entities."""
    clean_path = file_path.replace("\\", "/")
    raw = f"{repo_id}:{clean_path}:{qualified_name}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))


def generate_chunk_id(repo_id: str, file_path: str, start_line: int, end_line: int, symbol_name: str = "") -> str:
    """Generate deterministic UUID string for code chunks (valid for Qdrant point IDs)."""
    clean_path = file_path.replace("\\", "/")
    raw = f"{repo_id}:{clean_path}:{start_line}:{end_line}:{symbol_name}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))


class PythonASTParser(BaseParser):
    """Parser for Python source code using built-in ast module."""

    def parse_file(self, source_file: SourceFile, content: str, repository_id: str) -> ExtractedCodeData:
        """Parses Python file content into structured entities, relations, and symbol-aware chunks."""
        clean_rel_path = source_file.relative_path.replace("\\", "/")
        try:
            tree = ast.parse(content, filename=clean_rel_path)
        except SyntaxError as e:
            logger.warning(f"Syntax error parsing {clean_rel_path}: {e}")
            return ExtractedCodeData(repository_id=repository_id, file_info=source_file)
        except Exception as e:
            raise ParserError(f"Unexpected error parsing {clean_rel_path}: {e}")

        # Determine module qualified name
        mod_rel_path = clean_rel_path.removesuffix(".py")
        mod_name = mod_rel_path.replace("/", ".")
        if mod_name.endswith(".__init__"):
            mod_name = mod_name.removesuffix(".__init__")

        # Run relationship visitor
        visitor = ASTRelationshipVisitor(file_path=clean_rel_path, module_name=mod_name)
        visitor.visit(tree)

        lines = content.splitlines(keepends=True)
        symbols: list[CodeSymbol] = []
        chunks: list[CodeChunk] = []

        # Extract Module docstring & module symbol
        module_doc = ast.get_docstring(tree)
        module_symbol_id = generate_symbol_id(repository_id, clean_rel_path, mod_name)
        module_symbol = CodeSymbol(
            symbol_id=module_symbol_id,
            symbol_name=mod_name,
            symbol_type=SymbolType.MODULE,
            file_path=clean_rel_path,
            start_line=1,
            end_line=len(lines) if lines else 1,
            qualified_name=mod_name,
            docstring=module_doc,
        )
        symbols.append(module_symbol)

        # Iterate top-level & nested AST nodes to construct Class/Function/Method entities & chunks
        self._traverse_ast_nodes(
            nodes=tree.body,
            parent_qn=mod_name,
            repo_id=repository_id,
            source_file=source_file,
            lines=lines,
            symbols=symbols,
            chunks=chunks,
        )

        return ExtractedCodeData(
            repository_id=repository_id,
            file_info=source_file,
            symbols=symbols,
            imports=visitor.imports,
            calls=visitor.calls,
            inheritance=visitor.inheritance,
            chunks=chunks,
        )

    def _traverse_ast_nodes(
        self,
        nodes: Sequence[ast.AST],
        parent_qn: str,
        repo_id: str,
        source_file: SourceFile,
        lines: list[str],
        symbols: list[CodeSymbol],
        chunks: list[CodeChunk],
        enclosing_class: str | None = None,
    ):
        """Recursively walk AST nodes to construct detailed symbols and symbol-aware chunks."""
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                self._process_class_def(node, parent_qn, repo_id, source_file, lines, symbols, chunks)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if enclosing_class:
                    self._process_method_def(node, parent_qn, enclosing_class, repo_id, source_file, lines, symbols, chunks)
                else:
                    self._process_function_def(node, parent_qn, repo_id, source_file, lines, symbols, chunks)

    def _get_start_line(self, node: ast.AST) -> int:
        """Get the starting line number for an AST node, accounting for decorator lines."""
        lineno = getattr(node, "lineno", 1)
        decorator_list = getattr(node, "decorator_list", [])
        if decorator_list:
            dec_lines = [getattr(d, "lineno", lineno) for d in decorator_list]
            return min([lineno] + dec_lines)
        return lineno

    def _extract_params(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        """Extract all function/method parameter names including pos-only, vararg, kw-only, kwarg."""
        params: list[str] = []
        if not hasattr(node, "args"):
            return params

        for arg in getattr(node.args, "posonlyargs", []):
            params.append(arg.arg)
        for arg in getattr(node.args, "args", []):
            params.append(arg.arg)
        if node.args.vararg:
            params.append(f"*{node.args.vararg.arg}")
        for arg in getattr(node.args, "kwonlyargs", []):
            params.append(arg.arg)
        if node.args.kwarg:
            params.append(f"**{node.args.kwarg.arg}")
        return params

    def _process_class_def(
        self,
        node: ast.ClassDef,
        parent_qn: str,
        repo_id: str,
        source_file: SourceFile,
        lines: list[str],
        symbols: list[CodeSymbol],
        chunks: list[CodeChunk],
    ):
        clean_rel_path = source_file.relative_path.replace("\\", "/")
        qn = f"{parent_qn}.{node.name}"
        symbol_id = generate_symbol_id(repo_id, clean_rel_path, qn)
        start_line = self._get_start_line(node)
        end_line = getattr(node, "end_lineno", start_line) or start_line
        doc = ast.get_docstring(node)

        base_classes = [name for b in node.bases if (name := self._get_expr_name(b))]
        decorators = [dec for d in node.decorator_list if (dec := self._get_expr_name(d))]

        # Collect methods in class body
        method_qns = []
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_qns.append(f"{qn}.{child.name}")

        class_info = ClassInfo(
            symbol_id=symbol_id,
            symbol_name=node.name,
            file_path=clean_rel_path,
            start_line=start_line,
            end_line=end_line,
            qualified_name=qn,
            docstring=doc,
            parent_symbol=parent_qn,
            base_classes=base_classes,
            methods=method_qns,
            decorators=decorators,
        )
        symbols.append(class_info)

        # Generate class CodeChunk
        chunk_snippet = "".join(lines[max(0, start_line - 1) : min(len(lines), end_line)])
        chunks.append(
            CodeChunk(
                chunk_id=generate_chunk_id(repo_id, clean_rel_path, start_line, end_line, node.name),
                repository_id=repo_id,
                file_path=clean_rel_path,
                language=source_file.language,
                module=parent_qn,
                symbol_name=node.name,
                symbol_type="Class",
                start_line=start_line,
                end_line=end_line,
                content=chunk_snippet,
                parent_symbol=parent_qn,
            )
        )

        # Recurse class body for methods & nested classes
        self._traverse_ast_nodes(
            nodes=node.body,
            parent_qn=qn,
            repo_id=repo_id,
            source_file=source_file,
            lines=lines,
            symbols=symbols,
            chunks=chunks,
            enclosing_class=node.name,
        )

    def _process_function_def(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        parent_qn: str,
        repo_id: str,
        source_file: SourceFile,
        lines: list[str],
        symbols: list[CodeSymbol],
        chunks: list[CodeChunk],
    ):
        clean_rel_path = source_file.relative_path.replace("\\", "/")
        name = getattr(node, "name", "func")
        qn = f"{parent_qn}.{name}"
        symbol_id = generate_symbol_id(repo_id, clean_rel_path, qn)
        start_line = self._get_start_line(node)
        end_line = getattr(node, "end_lineno", start_line) or start_line
        doc = ast.get_docstring(node)

        params = self._extract_params(node)
        ret_type = self._get_expr_name(node.returns) if getattr(node, "returns", None) else None
        decorators = [dec for d in node.decorator_list if (dec := self._get_expr_name(d))]

        func_info = FunctionInfo(
            symbol_id=symbol_id,
            symbol_name=name,
            file_path=clean_rel_path,
            start_line=start_line,
            end_line=end_line,
            qualified_name=qn,
            docstring=doc,
            parent_symbol=parent_qn,
            parameters=params,
            return_type=ret_type,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            decorators=decorators,
        )
        symbols.append(func_info)

        chunk_snippet = "".join(lines[max(0, start_line - 1) : min(len(lines), end_line)])
        chunks.append(
            CodeChunk(
                chunk_id=generate_chunk_id(repo_id, clean_rel_path, start_line, end_line, name),
                repository_id=repo_id,
                file_path=clean_rel_path,
                language=source_file.language,
                module=parent_qn,
                symbol_name=name,
                symbol_type="Function",
                start_line=start_line,
                end_line=end_line,
                content=chunk_snippet,
                parent_symbol=parent_qn,
            )
        )

        # Recurse function body for inner functions or classes
        self._traverse_ast_nodes(
            nodes=node.body,
            parent_qn=qn,
            repo_id=repo_id,
            source_file=source_file,
            lines=lines,
            symbols=symbols,
            chunks=chunks,
            enclosing_class=None,
        )

    def _process_method_def(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        parent_qn: str,
        enclosing_class: str,
        repo_id: str,
        source_file: SourceFile,
        lines: list[str],
        symbols: list[CodeSymbol],
        chunks: list[CodeChunk],
    ):
        clean_rel_path = source_file.relative_path.replace("\\", "/")
        name = getattr(node, "name", "method")
        qn = f"{parent_qn}.{name}"
        symbol_id = generate_symbol_id(repo_id, clean_rel_path, qn)
        start_line = self._get_start_line(node)
        end_line = getattr(node, "end_lineno", start_line) or start_line
        doc = ast.get_docstring(node)

        params = self._extract_params(node)
        ret_type = self._get_expr_name(node.returns) if getattr(node, "returns", None) else None
        decorators = [dec for d in node.decorator_list if (dec := self._get_expr_name(d))]

        is_classmethod = any("classmethod" in d for d in decorators)
        is_staticmethod = any("staticmethod" in d for d in decorators)

        method_info = MethodInfo(
            symbol_id=symbol_id,
            symbol_name=name,
            file_path=clean_rel_path,
            start_line=start_line,
            end_line=end_line,
            qualified_name=qn,
            docstring=doc,
            parent_symbol=parent_qn,
            class_name=enclosing_class,
            parameters=params,
            return_type=ret_type,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            is_classmethod=is_classmethod,
            is_staticmethod=is_staticmethod,
            decorators=decorators,
        )
        symbols.append(method_info)

        chunk_snippet = "".join(lines[max(0, start_line - 1) : min(len(lines), end_line)])
        chunks.append(
            CodeChunk(
                chunk_id=generate_chunk_id(repo_id, clean_rel_path, start_line, end_line, name),
                repository_id=repo_id,
                file_path=clean_rel_path,
                language=source_file.language,
                module=parent_qn,
                symbol_name=name,
                symbol_type="Method",
                start_line=start_line,
                end_line=end_line,
                content=chunk_snippet,
                parent_symbol=parent_qn,
            )
        )

        # Recurse method body for inner functions or classes
        self._traverse_ast_nodes(
            nodes=node.body,
            parent_qn=qn,
            repo_id=repo_id,
            source_file=source_file,
            lines=lines,
            symbols=symbols,
            chunks=chunks,
            enclosing_class=None,
        )

    def _get_expr_name(self, node: ast.AST | None) -> str | None:
        """Convert AST expression node into readable name string."""
        if node is None:
            return None
        try:
            return ast.unparse(node).strip()
        except Exception:
            if isinstance(node, ast.Name):
                return node.id
            elif isinstance(node, ast.Attribute):
                val = self._get_expr_name(node.value)
                return f"{val}.{node.attr}" if val else node.attr
            elif isinstance(node, ast.Constant):
                return str(node.value)
            return None
