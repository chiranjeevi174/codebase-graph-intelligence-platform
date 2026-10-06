"""Go Tree-sitter code parser adapter."""

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


class GoParser(TreeSitterBaseParser):
    """Parser implementation for Go source files using Tree-sitter."""

    def __init__(self, language: str = "go", ts_language_name: str = "go"):
        super().__init__(language=language, ts_language_name=ts_language_name)

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
        package_name = ""

        # First pass: package_clause
        for child in root_node.children:
            if child.type == "package_clause":
                pkg_id = child.child_by_field_name("name") or (child.children[1] if len(child.children) > 1 else None)
                if pkg_id:
                    package_name = self._node_text(pkg_id, content_bytes).strip()
                break

        if not package_name:
            clean = file_path.replace("\\", "/").removesuffix(".go")
            package_name = clean.replace("/", ".")

        def walk(node: Any, scope: list[str]):
            current_caller = ".".join(scope) if scope else package_name
            node_type = node.type

            # 1. Imports
            if node_type == "import_declaration":
                start_line, _ = self._line_range(node)
                for child in node.children:
                    if child.type == "import_spec":
                        path_node = child.child_by_field_name("path") or child.children[-1]
                        mod_name = self._node_text(path_node, content_bytes).strip('"')
                        alias_node = child.child_by_field_name("name")
                        alias = self._node_text(alias_node, content_bytes) if alias_node else None

                        imports.append(
                            ImportInfo(
                                file_path=file_path,
                                module_name=mod_name,
                                alias=alias,
                                line_number=start_line,
                            )
                        )

            # 2. Structs & Interfaces (type_declaration)
            elif node_type == "type_declaration":
                for spec in node.children:
                    if spec.type == "type_spec":
                        name_node = spec.child_by_field_name("name") or spec.children[0]
                        type_name = self._node_text(name_node, content_bytes)
                        type_qn = f"{package_name}.{type_name}"
                        start_line, end_line = self._line_range(spec)

                        type_node = spec.child_by_field_name("type") or (
                            spec.children[1] if len(spec.children) > 1 else None
                        )
                        if type_node:
                            if type_node.type == "struct_type":
                                struct_sym = ClassInfo(
                                    symbol_id=generate_symbol_id(repository_id, file_path, type_qn),
                                    symbol_name=type_name,
                                    symbol_type=SymbolType.STRUCT,
                                    file_path=file_path,
                                    start_line=start_line,
                                    end_line=end_line,
                                    qualified_name=type_qn,
                                    parent_symbol=package_name,
                                )
                                symbols.append(struct_sym)
                            elif type_node.type == "interface_type":
                                iface_sym = CodeSymbol(
                                    symbol_id=generate_symbol_id(repository_id, file_path, type_qn),
                                    symbol_name=type_name,
                                    symbol_type=SymbolType.INTERFACE,
                                    file_path=file_path,
                                    start_line=start_line,
                                    end_line=end_line,
                                    qualified_name=type_qn,
                                    parent_symbol=package_name,
                                )
                                symbols.append(iface_sym)

            # 3. Methods (func with receiver)
            elif node_type == "method_declaration":
                receiver_node = node.child_by_field_name("receiver")
                receiver_type = ""
                if receiver_node:
                    for child in receiver_node.children:
                        if child.type == "parameter_declaration":
                            type_child = child.child_by_field_name("type") or child.children[-1]
                            raw_type = self._node_text(type_child, content_bytes)
                            receiver_type = raw_type.lstrip("*").strip()

                m_name_node = node.child_by_field_name("name")
                if m_name_node:
                    m_name = self._node_text(m_name_node, content_bytes)
                    if receiver_type:
                        m_qn = f"{package_name}.{receiver_type}.{m_name}"
                        parent_sym = f"{package_name}.{receiver_type}"
                    else:
                        m_qn = f"{package_name}.{m_name}"
                        parent_sym = package_name

                    start_line, end_line = self._line_range(node)

                    method_sym = MethodInfo(
                        symbol_id=generate_symbol_id(repository_id, file_path, m_qn),
                        symbol_name=m_name,
                        symbol_type=SymbolType.METHOD,
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        qualified_name=m_qn,
                        parent_symbol=parent_sym,
                        class_name=receiver_type or package_name,
                    )
                    symbols.append(method_sym)
                    walk(
                        node.child_by_field_name("body") or node,
                        scope + ([receiver_type, m_name] if receiver_type else [m_name]),
                    )
                    return

            # 4. Top-level Functions
            elif node_type == "function_declaration":
                fn_name_node = node.child_by_field_name("name")
                if fn_name_node:
                    fn_name = self._node_text(fn_name_node, content_bytes)
                    fn_qn = f"{package_name}.{fn_name}"
                    start_line, end_line = self._line_range(node)

                    func_sym = FunctionInfo(
                        symbol_id=generate_symbol_id(repository_id, file_path, fn_qn),
                        symbol_name=fn_name,
                        symbol_type=SymbolType.FUNCTION,
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        qualified_name=fn_qn,
                        parent_symbol=package_name,
                    )
                    symbols.append(func_sym)
                    walk(node.child_by_field_name("body") or node, scope + [fn_name])
                    return

            # 5. Calls
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

        walk(root_node, [package_name] if package_name else [])
