"""Unit tests for Python AST parser and relationship extractor."""

from app.models.entities import ClassInfo, FunctionInfo, MethodInfo, SourceFile, SymbolType
from app.parsing.python_parser import PythonASTParser


def test_python_ast_parser_extraction(sample_python_code):
    source_file = SourceFile(
        file_path="app/sample.py",
        relative_path="app/sample.py",
        language="python",
        size_bytes=len(sample_python_code),
        lines_of_code=len(sample_python_code.splitlines()),
        extension=".py",
    )

    parser = PythonASTParser()
    extracted = parser.parse_file(source_file, sample_python_code, repository_id="test_repo")

    # Verify Module symbol
    assert len(extracted.symbols) > 0
    mod_symbol = extracted.symbols[0]
    assert mod_symbol.symbol_type == SymbolType.MODULE

    # Check extracted classes
    classes = [s for s in extracted.symbols if isinstance(s, ClassInfo)]
    class_names = [c.symbol_name for c in classes]
    assert "BaseService" in class_names
    assert "UserService" in class_names

    # Check extracted top-level functions
    funcs = [s for s in extracted.symbols if isinstance(s, FunctionInfo)]
    func_names = [f.symbol_name for f in funcs]
    assert "calculate_tax" in func_names

    # Check extracted methods
    methods = [s for s in extracted.symbols if isinstance(s, MethodInfo)]
    method_names = [m.symbol_name for m in methods]
    assert "get_status" in method_names
    assert "fetch_user" in method_names
    assert "create_default" in method_names

    # Check imports
    imported_modules = [imp.module_name for imp in extracted.imports]
    assert "os" in imported_modules
    assert "typing" in imported_modules

    # Check inheritance relations
    inh_child_names = [inh.child_qualified_name for inh in extracted.inheritance]
    assert any("UserService" in child for child in inh_child_names)
    assert extracted.inheritance[0].parent_name == "BaseService"

    # Check symbol-aware chunks
    assert len(extracted.chunks) > 0
    chunk_types = [c.symbol_type for c in extracted.chunks]
    assert "Class" in chunk_types
    assert "Function" in chunk_types or "Method" in chunk_types


def test_python_ast_parser_advanced_features():
    code = '''
from typing import Generic, TypeVar

T = TypeVar("T")

@decorator_with_call(arg=123)
class Container(Generic[T]):
    def __init__(self, pos_only, /, normal_arg, *args, kw_only=1, **kwargs) -> str | None:
        def inner_helper():
            pass
        self.val = normal_arg
'''
    source_file = SourceFile(
        file_path="app\\nested\\container.py",
        relative_path="app\\nested\\container.py",
        language="python",
        size_bytes=len(code),
        lines_of_code=len(code.splitlines()),
        extension=".py",
    )
    parser = PythonASTParser()
    extracted = parser.parse_file(source_file, code, repository_id="repo1")

    classes = [s for s in extracted.symbols if isinstance(s, ClassInfo)]
    assert len(classes) == 1
    cls = classes[0]
    assert cls.symbol_name == "Container"
    assert "Generic[T]" in cls.base_classes
    assert any("decorator_with_call" in d for d in cls.decorators)

    methods = [s for s in extracted.symbols if isinstance(s, MethodInfo)]
    assert len(methods) == 1
    m = methods[0]
    assert m.symbol_name == "__init__"
    assert m.parameters == ["self", "pos_only", "normal_arg", "*args", "kw_only", "**kwargs"]
    assert m.return_type == "str | None"

    funcs = [s for s in extracted.symbols if isinstance(s, FunctionInfo)]
    func_names = [f.symbol_name for f in funcs]
    assert "inner_helper" in func_names

