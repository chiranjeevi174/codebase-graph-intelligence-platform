"""Unit tests for TypeScript tree-sitter parser adapter."""

from app.models.entities import SourceFile, SymbolType
from app.parsing.typescript_parser import TypeScriptParser


def test_typescript_parser_extraction():
    parser = TypeScriptParser()
    source_file = SourceFile(
        file_path="src/service.ts",
        relative_path="src/service.ts",
        language="typescript",
        size_bytes=250,
        lines_of_code=20,
        extension=".ts",
    )
    content = """
    import { Base } from "./base";

    export interface UserInterface {
        id: string;
    }

    export class TSUserService extends Base implements UserInterface {
        id: string = "1";
        createUser(name: string): void {
            this.log(name);
        }
    }
    """

    data = parser.parse_file(source_file, content, "repo1")

    # Check interface and class
    sym_types = {s.symbol_name: s.symbol_type for s in data.symbols}
    assert "UserInterface" in sym_types
    assert sym_types["UserInterface"] == SymbolType.INTERFACE
    assert "TSUserService" in sym_types
    assert sym_types["TSUserService"] == SymbolType.CLASS

    # Check extends and implements
    rel_types = [inh.relationship_type for inh in data.inheritance]
    assert "INHERITS" in rel_types
    assert "IMPLEMENTS" in rel_types

    # Check imports
    assert len(data.imports) >= 1
    assert data.imports[0].module_name == "./base"
