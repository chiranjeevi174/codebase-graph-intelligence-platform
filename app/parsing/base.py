"""Parser abstract base class."""

from abc import ABC, abstractmethod

from app.models.entities import ExtractedCodeData, SourceFile


class BaseParser(ABC):
    """Abstract interface for source code parsers."""

    @abstractmethod
    def parse_file(self, source_file: SourceFile, content: str, repository_id: str) -> ExtractedCodeData:
        """Parse source code content and extract symbols, relationships, and code chunks.

        Args:
            source_file: Metadata of the source file.
            content: Raw source code text.
            repository_id: Identifier of repository being parsed.

        Returns:
            ExtractedCodeData container.
        """
