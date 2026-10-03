"""AST Relationship Extractor using Python standard library ast module."""

import ast

from app.models.entities import CallRelation, ImportInfo, InheritanceRelation


class ASTRelationshipVisitor(ast.NodeVisitor):
    """AST NodeVisitor to extract imports, function/method calls, and inheritance relationships."""

    def __init__(self, file_path: str, module_name: str):
        self.file_path = file_path
        self.module_name = module_name
        self.imports: list[ImportInfo] = []
        self.calls: list[CallRelation] = []
        self.inheritance: list[InheritanceRelation] = []
        self._current_scope: list[str] = [module_name]

    def _get_current_caller(self) -> str:
        return ".".join(self._current_scope)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(
                ImportInfo(
                    file_path=self.file_path,
                    module_name=alias.name,
                    alias=alias.asname,
                    line_number=node.lineno,
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        for alias in node.names:
            self.imports.append(
                ImportInfo(
                    file_path=self.file_path,
                    module_name=mod,
                    imported_symbol=alias.name,
                    alias=alias.asname,
                    line_number=node.lineno,
                )
            )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        class_qualified_name = f"{self._get_current_caller()}.{node.name}"
        for base in node.bases:
            parent_name = self._get_name_from_node(base)
            if parent_name:
                self.inheritance.append(
                    InheritanceRelation(
                        child_qualified_name=class_qualified_name,
                        parent_name=parent_name,
                        file_path=self.file_path,
                    )
                )

        self._current_scope.append(node.name)
        self.generic_visit(node)
        self._current_scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._current_scope.append(node.name)
        self.generic_visit(node)
        self._current_scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._current_scope.append(node.name)
        self.generic_visit(node)
        self._current_scope.pop()

    def visit_Call(self, node: ast.Call):
        caller_qn = self._get_current_caller()
        callee_name = self._get_name_from_node(node.func)
        if callee_name:
            self.calls.append(
                CallRelation(
                    caller_qualified_name=caller_qn,
                    callee_name=callee_name,
                    line_number=node.lineno,
                    file_path=self.file_path,
                )
            )
        self.generic_visit(node)

    def _get_name_from_node(self, node: ast.AST) -> str | None:
        """Utility to extract human-readable name from AST nodes (Name, Attribute, Call)."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value_name = self._get_name_from_node(node.value)
            if value_name:
                return f"{value_name}.{node.attr}"
            return node.attr
        elif isinstance(node, ast.Call):
            return self._get_name_from_node(node.func)
        return None
