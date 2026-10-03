"""Unit tests for JavaScript tree-sitter parser adapter."""

from app.models.entities import SourceFile
from app.parsing.javascript_parser import JavaScriptParser


def test_javascript_parser_extraction():
    parser = JavaScriptParser()
    source_file = SourceFile(
        file_path="src/service.js",
        relative_path="src/service.js",
        language="javascript",
        size_bytes=200,
        lines_of_code=15,
        extension=".js",
    )
    content = """
    class BaseLogger {
        log(msg) {
            console.log(msg);
        }
    }
    class JSUserService extends BaseLogger {
        createUser(name) {
            this.log(name);
        }
    }
    const { helper } = require("./utils");
    """

    data = parser.parse_file(source_file, content, "repo1")

    # Check symbols
    symbol_names = [s.symbol_name for s in data.symbols]
    assert "BaseLogger" in symbol_names
    assert "JSUserService" in symbol_names
    assert "createUser" in symbol_names

    # Check inheritance
    assert len(data.inheritance) >= 1
    assert data.inheritance[0].parent_name == "BaseLogger"
    assert data.inheritance[0].relationship_type == "INHERITS"

    # Check imports
    assert len(data.imports) >= 1
    assert data.imports[0].module_name == "./utils"

    # Check chunks created
    assert len(data.chunks) > 0
    assert data.chunks[0].language == "javascript"
