"""Unit tests for Java tree-sitter parser adapter."""

from app.models.entities import SourceFile
from app.parsing.java_parser import JavaParser


def test_java_parser_extraction():
    parser = JavaParser()
    source_file = SourceFile(
        file_path="com/example/service/UserService.java",
        relative_path="com/example/service/UserService.java",
        language="java",
        size_bytes=300,
        lines_of_code=20,
        extension=".java",
    )
    content = """
    package com.example.service;

    import com.example.model.User;

    public interface UserOperation {
        void processUser(String name);
    }

    public class UserService extends BaseService implements UserOperation {
        public UserService() {}

        @Override
        public void processUser(String name) {
            logMessage(name);
        }
    }
    """

    data = parser.parse_file(source_file, content, "repo1")

    # Check package and symbols
    symbol_names = [s.symbol_name for s in data.symbols]
    assert "UserOperation" in symbol_names
    assert "UserService" in symbol_names
    assert "processUser" in symbol_names

    # Check qualified names contain package
    qn_list = [s.qualified_name for s in data.symbols]
    assert any("com.example.service.UserService" in qn for qn in qn_list)

    # Check inheritance & interface implementation
    rel_types = [inh.relationship_type for inh in data.inheritance]
    assert "INHERITS" in rel_types
    assert "IMPLEMENTS" in rel_types

    # Check calls
    assert len(data.calls) >= 1
    assert data.calls[0].callee_name == "logMessage"
