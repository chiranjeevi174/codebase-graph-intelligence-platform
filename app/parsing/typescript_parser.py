"""TypeScript Tree-sitter code parser adapter."""

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


class TypeScriptParser(TreeSitterBaseParser):
    """Parser implementation for TypeScript source files using Tree-sitter."""

    def __init__(self, language: str = "typescript", ts_language_name: str = "typescript"):
        super().__init__(language=language, ts_language_name=ts_language_name)

    def _get_module_path(self, file_path: str) -> str:
        clean = file_path.replace("\\", "/")
        for ext in [".tsx", ".ts", ".jsx", ".js"]:
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
                    elif child.type in ["identifier", "type_identifier"]:
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

            # 2. Interfaces
            elif node_type == "interface_declaration":
                name_node = node.child_by_field_name("name") or (node.children[1] if len(node.children) > 1 else None)
                if name_node:
                    iface_name = self._node_text(name_node, content_bytes)
                    iface_qn = f"{module_qn}.{iface_name}"
                    start_line, end_line = self._line_range(node)

                    # Interface extends
                    heritage = node.child_by_field_name("heritage")
                    if not heritage:
                        for c in node.children:
                            if c.type in ["extends_clause", "interface_heritage"]:
                                heritage = c
                                break

                    if heritage:
                        for c in heritage.children:
                            if c.type in ["extends_clause", "type_identifier", "identifier"]:
                                parent_name = self._node_text(c, content_bytes).replace("extends", "").strip()
                                if parent_name:
                                    inheritance.append(
                                        InheritanceRelation(
                                            child_qualified_name=iface_qn,
                                            parent_name=parent_name,
                                            file_path=file_path,
                                            relationship_type="INHERITS",
                                        )
                                    )

                    iface_sym = CodeSymbol(
                        symbol_id=generate_symbol_id(repository_id, file_path, iface_qn),
                        symbol_name=iface_name,
                        symbol_type=SymbolType.INTERFACE,
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        qualified_name=iface_qn,
                        parent_symbol=module_qn,
                    )
                    symbols.append(iface_sym)

            # 3. Type Aliases
            elif node_type == "type_alias_declaration":
                name_node = node.child_by_field_name("name") or (node.children[1] if len(node.children) > 1 else None)
                if name_node:
                    type_name = self._node_text(name_node, content_bytes)
                    type_qn = f"{module_qn}.{type_name}"
                    start_line, end_line = self._line_range(node)

                    type_sym = CodeSymbol(
                        symbol_id=generate_symbol_id(repository_id, file_path, type_qn),
                        symbol_name=type_name,
                        symbol_type=SymbolType.TYPE_ALIAS,
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        qualified_name=type_qn,
                        parent_symbol=module_qn,
                    )
                    symbols.append(type_sym)

            # 4. Classes
            elif node_type == "class_declaration":
                name_node = node.child_by_field_name("name") or (node.children[1] if len(node.children) > 1 else None)
                class_name = self._node_text(name_node, content_bytes) if name_node else "AnonymousClass"
                class_qn = f"{module_qn}.{class_name}"
                start_line, end_line = self._line_range(node)

                base_classes = []
                heritage = node.child_by_field_name("heritage") or (
                    node.children[2] if len(node.children) > 2 else None
                )
                if heritage and hasattr(heritage, "children"):
                    for c in heritage.children:
                        if c.type == "extends_clause":
                            val = self._node_text(c, content_bytes).replace("extends", "").strip()
                            if val:
                                base_classes.append(val)
                                inheritance.append(
                                    InheritanceRelation(
                                        child_qualified_name=class_qn,
                                        parent_name=val,
                                        file_path=file_path,
                                        relationship_type="INHERITS",
                                    )
                                )
                        elif c.type == "implements_clause":
                            val = self._node_text(c, content_bytes).replace("implements", "").strip()
                            if val:
                                for impl_item in val.split(","):
                                    clean_impl = impl_item.strip()
                                    if clean_impl:
                                        inheritance.append(
                                            InheritanceRelation(
                                                child_qualified_name=class_qn,
                                                parent_name=clean_impl,
                                                file_path=file_path,
                                                relationship_type="IMPLEMENTS",
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

                body_node = node.child_by_field_name("body") or (node.children[-1] if node.children else None)
                if body_node and hasattr(body_node, "children"):
                    for member in body_node.children:
                        if member.type == "method_definition":
                            m_name_node = member.child_by_field_name("name") or member.children[0]
                            m_name = self._node_text(m_name_node, content_bytes)
                            m_qn = f"{class_qn}.{m_name}"
                            m_start, m_end = self._line_range(member)

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
                            )
                            symbols.append(method_sym)
                            walk(member, scope + [class_name, m_name])
                    return

            # 5. Functions
            elif node_type == "function_declaration":
                fn_name_node = node.child_by_field_name("name") or (
                    node.children[1] if len(node.children) > 1 else None
                )
                if fn_name_node:
                    fn_name = self._node_text(fn_name_node, content_bytes)
                    fn_qn = f"{module_qn}.{fn_name}"
                    start_line, end_line = self._line_range(node)

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
                    walk(node.child_by_field_name("body") or node, scope + [fn_name])
                    return

            # 6. Function Calls
            elif node_type == "call_expression":
                fn_node = node.child_by_field_name("function") or (node.children[0] if node.children else None)
                fn_text = self._node_text(fn_node, content_bytes)
                start_line, _ = self._line_range(node)
                if fn_text:
                    callee_name = fn_text.split(".")[-1]
                    calls.append(
                        CallRelation(
                            caller_qualified_name=current_caller,
                            callee_name=callee_name,
                            line_number=start_line,
                            file_path=file_path,
                        )
                    )

            for child in node.children:
                walk(child, scope)

        walk(root_node, [])
