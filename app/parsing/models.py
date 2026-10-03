"""Parser configuration and intermediate parsing models."""

from pydantic import BaseModel


class ParserConfig(BaseModel):
    """Configuration options for AST parsers."""
    extract_docstrings: bool = True
    extract_calls: bool = True
    extract_imports: bool = True
    max_chunk_lines: int = 100
    min_chunk_lines: int = 3
