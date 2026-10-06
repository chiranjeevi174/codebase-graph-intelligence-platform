"""JavaScript Tree-sitter code parser adapter."""

from typing import Any

from app.models.entities import (
    CallRelation,
    ClassInfo,
    CodeSymbol,
    FunctionInfo,
    ImportInfo,
    InheritanceRelation,
    MethodInfo,
    SymbolType,
)
from app.parsing.tree_sitter_base import TreeSitterBaseParser, generate_symbol_id


class JavaScriptParser(TreeSitterBaseParser):
    """Parser implementation for JavaScript source files using Tree-sitter."""

    def __init__(self, language: str = "javascript", ts_language_name: str = "javascript"):
        super().__init__(language=language, ts_language_name=ts_language_name)

    def _get_module_path(self, file_path: str) -> str:
        clean = file_path.replace("\\", "/")
        for ext in [".jsx", ".js", ".mjs", ".cjs", ".ts", ".tsx"]:
            if clean.endswith(ext):
                clean = clean[: -len(ext)]
                break
        return clean.replace("/", ".")

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
        module_qn = self._get_module_path(file_path)

        def walk(node: Any, scope: list[str]):
            current_caller = ".".join(scope) if scope else module_qn
            node_type = node.type

            # 1. Imports
            if node_type == "import_statement":
                source_node = node.child_by_field_name("source")
                mod_source = self._node_text(source_node, content_bytes).strip("'\"`") if source_node else ""

                start_line, _ = self._line_range(node)
                import_clause = node.child_by_field_name("clause") or node

                imported_symbols = []
                for child in import_clause.children:
                    if child.type == "named_imports":
                        for spec in child.children:
                            if spec.type == "import_specifier":
                                name_child = spec.child_by_field_name("name") or spec.children[0]
                                imported_symbols.append(self._node_text(name_child, content_bytes))
                    elif child.type == "identifier":
                        imported_symbols.append(self._node_text(child, content_bytes))

                if imported_symbols:
                    for sym_name in imported_symbols:
                        imports.append(
                            ImportInfo(
                                file_path=file_path,
                                module_name=mod_source,
                                imported_symbol=sym_name,
                                line_number=start_line,
                            )
                        )
                else:
                    imports.append(
                        ImportInfo(
                            file_path=file_path,
                            module_name=mod_source,
                            line_number=start_line,
                        )
                    )

            # Require calls: const x = require('y')
            elif node_type == "call_expression":
                fn_node = node.child_by_field_name("function") or (node.children[0] if node.children else None)
                fn_text = self._node_text(fn_node, content_bytes)
                start_line, _ = self._line_range(node)

                if fn_text == "require":
                    args = node.child_by_field_name("arguments") or (
                        node.children[1] if len(node.children) > 1 else None
                    )
                    if args and args.children:
                        mod_name = self._node_text(
                            args.children[1] if len(args.children) > 1 else args.children[0], content_bytes
                        ).strip("'\"`")
                        imports.append(
                            ImportInfo(
                                file_path=file_path,
                                module_name=mod_name,
                                line_number=start_line,
                            )
                        )
                elif fn_text:
                    callee_name = fn_text.split(".")[-1]
                    calls.append(
                        CallRelation(
                            caller_qualified_name=current_caller,
                            callee_name=callee_name,
                            line_number=start_line,
                            file_path=file_path,
                        )
                    )

            # 2. Classes
            elif node_type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if not name_node:
                    for c in node.children:
                        if c.type in ["identifier", "type_identifier"]:
                            name_node = c
                            break

                class_name = self._node_text(name_node, content_bytes) if name_node else "AnonymousClass"
                class_qn = f"{module_qn}.{class_name}"
                start_line, end_line = self._line_range(node)

                # Inheritance check
                base_classes = []
                heritage = node.child_by_field_name("heritage")
                if not heritage:
                    for c in node.children:
                        if c.type == "class_heritage":
                            heritage = c
                            break

                if heritage:
                    for c in heritage.children:
                        if c.type in ["identifier", "property_identifier", "member_expression", "type_identifier"]:
                            parent_name = self._node_text(c, content_bytes)
                            base_classes.append(parent_name)
                            inheritance.append(
                                InheritanceRelation(
                                    child_qualified_name=class_qn,
                                    parent_name=parent_name,
                                    file_path=file_path,
                                    relationship_type="INHERITS",
                                )
                            )

                class_sym = ClassInfo(
                    symbol_id=generate_symbol_id(repository_id, file_path, class_qn),
                    symbol_name=class_name,
                    symbol_type=SymbolType.CLASS,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    qualified_name=class_qn,
                    parent_symbol=module_qn,
                    base_classes=base_classes,
                )
                symbols.append(class_sym)

                # Process methods inside class body
                body_node = node.child_by_field_name("body") or (node.children[-1] if node.children else None)
                if body_node:
                    for member in body_node.children:
                        if member.type == "method_definition":
                            m_name_node = member.child_by_field_name("name") or member.children[0]
                            m_name = self._node_text(m_name_node, content_bytes)
                            m_qn = f"{class_qn}.{m_name}"
                            m_start, m_end = self._line_range(member)

                            params = []
                            params_node = member.child_by_field_name("parameters")
                            if params_node:
                                params = [
                                    self._node_text(p, content_bytes)
                                    for p in params_node.children
                                    if p.type == "identifier"
                                ]

                            method_sym = MethodInfo(
                                symbol_id=generate_symbol_id(repository_id, file_path, m_qn),
                                symbol_name=m_name,
                                symbol_type=SymbolType.METHOD,
                                file_path=file_path,
                                start_line=m_start,
                                end_line=m_end,
                                qualified_name=m_qn,
                                parent_symbol=class_qn,
                                class_name=class_qn,
                                parameters=params,
                            )
                            symbols.append(method_sym)

                            # Walk inside method body for calls
                            walk(member, scope + [class_name, m_name])
                    return

            # 3. Functions
            elif node_type == "function_declaration":
                fn_name_node = node.child_by_field_name("name") or (
                    node.children[1] if len(node.children) > 1 else None
                )
                if fn_name_node and fn_name_node.type == "identifier":
                    fn_name = self._node_text(fn_name_node, content_bytes)
                    fn_qn = f"{module_qn}.{fn_name}"
                    start_line, end_line = self._line_range(node)

                    params = []
                    params_node = node.child_by_field_name("parameters")
                    if params_node:
                        params = [
                            self._node_text(p, content_bytes) for p in params_node.children if p.type == "identifier"
                        ]

                    func_sym = FunctionInfo(
                        symbol_id=generate_symbol_id(repository_id, file_path, fn_qn),
                        symbol_name=fn_name,
                        symbol_type=SymbolType.FUNCTION,
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        qualified_name=fn_qn,
                        parent_symbol=module_qn,
                        parameters=params,
                    )
                    symbols.append(func_sym)
                    walk(node.child_by_field_name("body") or node, scope + [fn_name])
                    return

            # Variable declarations with arrow functions / function expressions
            elif node_type in ["lexical_declaration", "variable_declaration"]:
                for declarator in node.children:
                    if declarator.type == "variable_declarator":
                        name_node = declarator.child_by_field_name("name")
                        value_node = declarator.child_by_field_name("value")
                        if name_node and value_node and value_node.type in ["arrow_function", "function_expression"]:
                            fn_name = self._node_text(name_node, content_bytes)
                            fn_qn = f"{module_qn}.{fn_name}"
                            start_line, end_line = self._line_range(declarator)

                            func_sym = FunctionInfo(
                                symbol_id=generate_symbol_id(repository_id, file_path, fn_qn),
                                symbol_name=fn_name,
                                symbol_type=SymbolType.FUNCTION,
                                file_path=file_path,
                                start_line=start_line,
                                end_line=end_line,
                                qualified_name=fn_qn,
                                parent_symbol=module_qn,
                            )
                            symbols.append(func_sym)
                            walk(value_node, scope + [fn_name])
                            return

            # Recurse children
            for child in node.children:
                walk(child, scope)

        walk(root_node, [])
