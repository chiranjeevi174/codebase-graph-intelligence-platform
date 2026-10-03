"""Unit tests for Go tree-sitter parser adapter."""

from app.models.entities import SourceFile, SymbolType
from app.parsing.go_parser import GoParser


def test_go_parser_extraction():
    parser = GoParser()
    source_file = SourceFile(
        file_path="service/user.go",
        relative_path="service/user.go",
        language="go",
        size_bytes=250,
        lines_of_code=20,
        extension=".go",
    )
    content = """
    package service

    import "fmt"

    type UserInterface interface {
        CreateUser()
    }

    type UserStruct struct {
        Name string
    }

    func (u *UserStruct) CreateUser() {
        fmt.Println("Created")
    }

    func NewUser() *UserStruct {
        return &UserStruct{}
    }
    """

    data = parser.parse_file(source_file, content, "repo1")

    # Check structs, interfaces, methods, functions
    sym_map = {s.symbol_name: s.symbol_type for s in data.symbols}
    assert "UserInterface" in sym_map
    assert sym_map["UserInterface"] == SymbolType.INTERFACE
    assert "UserStruct" in sym_map
    assert sym_map["UserStruct"] == SymbolType.STRUCT
    assert "CreateUser" in sym_map
    assert sym_map["CreateUser"] == SymbolType.METHOD
    assert "NewUser" in sym_map
    assert sym_map["NewUser"] == SymbolType.FUNCTION

    # Check imports
    assert len(data.imports) >= 1
    assert data.imports[0].module_name == "fmt"

    # Check method qualified name with receiver
    method_sym = [s for s in data.symbols if s.symbol_name == "CreateUser"][0]
    assert method_sym.qualified_name == "service.UserStruct.CreateUser"
