"""Unit tests for ParserFactory selecting language parsers."""

import pytest

from app.parsing import (
    GoParser,
    JavaParser,
    JavaScriptParser,
    ParserFactory,
    PythonASTParser,
    TypeScriptParser,
)
from app.utils.exceptions import ParserError


def test_parser_factory_python():
    parser = ParserFactory.get_parser("python")
    assert isinstance(parser, PythonASTParser)

    parser_ext = ParserFactory.get_parser(".py")
    assert isinstance(parser_ext, PythonASTParser)


def test_parser_factory_javascript():
    parser = ParserFactory.get_parser("javascript")
    assert isinstance(parser, JavaScriptParser)

    parser_jsx = ParserFactory.get_parser(".jsx")
    assert isinstance(parser_jsx, JavaScriptParser)


def test_parser_factory_typescript():
    parser = ParserFactory.get_parser("typescript")
    assert isinstance(parser, TypeScriptParser)

    parser_tsx = ParserFactory.get_parser(".tsx")
    assert isinstance(parser_tsx, TypeScriptParser)


def test_parser_factory_java():
    parser = ParserFactory.get_parser("java")
    assert isinstance(parser, JavaParser)

    parser_ext = ParserFactory.get_parser(".java")
    assert isinstance(parser_ext, JavaParser)


def test_parser_factory_go():
    parser = ParserFactory.get_parser("go")
    assert isinstance(parser, GoParser)

    parser_ext = ParserFactory.get_parser(".go")
    assert isinstance(parser_ext, GoParser)


def test_parser_factory_unsupported():
    with pytest.raises(ParserError):
        ParserFactory.get_parser("unsupported_lang_123")
