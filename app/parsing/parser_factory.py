"""Parser Factory for registering and obtaining language-specific code parsers."""

from typing import ClassVar

from app.models.entities import ExtractedCodeData, SourceFile
from app.parsing.base import BaseParser
from app.parsing.go_parser import GoParser
from app.parsing.java_parser import JavaParser
from app.parsing.javascript_parser import JavaScriptParser
from app.parsing.language import normalize_language
from app.parsing.python_parser import PythonASTParser
from app.parsing.typescript_parser import TypeScriptParser
from app.utils.exceptions import ParserError


class GenericSpecParser(BaseParser):
    """Parser for non-executable specification files (YAML, JSON)."""

    def parse_file(self, source_file: SourceFile, content: str, repository_id: str) -> ExtractedCodeData:
        return ExtractedCodeData(
            repository_id=repository_id,
            file_info=source_file,
            symbols=[],
            imports=[],
            calls=[],
            inheritance=[],
            chunks=[],
        )


class ParserFactory:
    """Factory and registry for language parsers."""

    _parsers: ClassVar[dict[str, type[BaseParser]]] = {
        "python": PythonASTParser,
        "javascript": JavaScriptParser,
        "typescript": TypeScriptParser,
        "java": JavaParser,
        "go": GoParser,
        "yaml": GenericSpecParser,
        "json": GenericSpecParser,
    }

    @classmethod
    def register_parser(cls, language: str, parser_cls: type[BaseParser]):
        """Register a new parser implementation for a programming language."""
        key = normalize_language(language)
        cls._parsers[key] = parser_cls

    @classmethod
    def get_parser(cls, language_or_extension: str) -> BaseParser:
        """Instantiate and return the appropriate parser for the specified language or extension."""
        lang_key = normalize_language(language_or_extension)
        parser_cls = cls._parsers.get(lang_key)
        if not parser_cls:
            raise ParserError(
                f"No parser registered for language/extension '{language_or_extension}'. "
                f"Supported languages: {list(cls._parsers.keys())}"
            )
        return parser_cls()
