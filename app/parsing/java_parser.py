"""Java Tree-sitter code parser adapter."""

from typing import Any

from app.models.entities import (
    CallRelation,
    ClassInfo,
    CodeSymbol,
    ImportInfo,
    InheritanceRelation,
    MethodInfo,
    SymbolType,
)
from app.parsing.tree_sitter_base import TreeSitterBaseParser, generate_symbol_id


class JavaParser(TreeSitterBaseParser):
    """Parser implementation for Java source files using Tree-sitter."""

    def __init__(self, language: str = "java", ts_language_name: str = "java"):
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

        # First pass: find package_declaration
        for child in root_node.children:
            if child.type == "package_declaration":
                pkg_id = child.child_by_field_name("name") or (child.children[1] if len(child.children) > 1 else None)
                if pkg_id:
                    package_name = self._node_text(pkg_id, content_bytes).strip()
                break

        if not package_name:
            clean = file_path.replace("\\", "/").removesuffix(".java")
            package_name = clean.replace("/", ".")

        def walk(node: Any, scope: list[str]):
            current_caller = ".".join(scope) if scope else package_name
            node_type = node.type

            # 1. Imports
            if node_type == "import_declaration":
                imp_id = node.child_by_field_name("name") or (node.children[1] if len(node.children) > 1 else None)
                if imp_id:
                    imp_text = self._node_text(imp_id, content_bytes).strip()
                    start_line, _ = self._line_range(node)
                    imports.append(
                        ImportInfo(
                            file_path=file_path,
                            module_name=imp_text,
                            line_number=start_line,
                        )
                    )

            # 2. Interfaces
            elif node_type == "interface_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    iface_name = self._node_text(name_node, content_bytes)
                    iface_qn = f"{package_name}.{iface_name}"
                    start_line, end_line = self._line_range(node)

                    # Extended interfaces
                    extends_node = node.child_by_field_name("extends")
                    if extends_node:
                        ext_text = self._node_text(extends_node, content_bytes).replace("extends", "").strip()
                        for parent in ext_text.split(","):
                            clean_parent = parent.strip()
                            if clean_parent:
                                inheritance.append(
                                    InheritanceRelation(
                                        child_qualified_name=iface_qn,
                                        parent_name=clean_parent,
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
                        parent_symbol=package_name,
                    )
                    symbols.append(iface_sym)

            # 3. Classes
            elif node_type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    class_name = self._node_text(name_node, content_bytes)
                    class_qn = f"{package_name}.{class_name}"
                    start_line, end_line = self._line_range(node)

                    base_classes = []
                    # Extends
                    super_node = node.child_by_field_name("superclass")
                    if super_node:
                        super_name = self._node_text(super_node, content_bytes).replace("extends", "").strip()
                        if super_name:
                            base_classes.append(super_name)
                            inheritance.append(
                                InheritanceRelation(
                                    child_qualified_name=class_qn,
                                    parent_name=super_name,
                                    file_path=file_path,
                                    relationship_type="INHERITS",
                                )
                            )

                    # Implements
                    interfaces_node = node.child_by_field_name("interfaces") or node.child_by_field_name(
                        "super_interfaces"
                    )
                    if interfaces_node:
                        impl_text = self._node_text(interfaces_node, content_bytes).replace("implements", "").strip()
                        for impl in impl_text.split(","):
                            clean_impl = impl.strip()
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
                        parent_symbol=package_name,
                        base_classes=base_classes,
                    )
                    symbols.append(class_sym)

                    # Class body
                    body_node = node.child_by_field_name("body")
                    if body_node:
                        for member in body_node.children:
                            if member.type == "method_declaration":
                                m_name_node = member.child_by_field_name("name")
                                if m_name_node:
                                    m_name = self._node_text(m_name_node, content_bytes)
                                    m_qn = f"{class_qn}.{m_name}"
                                    m_start, m_end = self._line_range(member)

                                    params = []
                                    params_node = member.child_by_field_name("parameters")
                                    if params_node:
                                        params = [
                                            self._node_text(p, content_bytes)
                                            for p in params_node.children
                                            if p.type == "formal_parameter"
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
                                    walk(member, scope + [class_name, m_name])

                            elif member.type == "constructor_declaration":
                                c_name_node = member.child_by_field_name("name")
                                if c_name_node:
                                    c_name = self._node_text(c_name_node, content_bytes)
                                    c_qn = f"{class_qn}.{c_name}"
                                    c_start, c_end = self._line_range(member)

                                    ctor_sym = MethodInfo(
                                        symbol_id=generate_symbol_id(repository_id, file_path, c_qn),
                                        symbol_name=c_name,
                                        symbol_type=SymbolType.CONSTRUCTOR,
                                        file_path=file_path,
                                        start_line=c_start,
                                        end_line=c_end,
                                        qualified_name=c_qn,
                                        parent_symbol=class_qn,
                                        class_name=class_qn,
                                    )
                                    symbols.append(ctor_sym)
                                    walk(member, scope + [class_name, c_name])

                        return

            # 4. Method Invocations
            elif node_type == "method_invocation":
                name_node = node.child_by_field_name("name")
                if name_node:
                    callee_name = self._node_text(name_node, content_bytes)
                    start_line, _ = self._line_range(node)
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
