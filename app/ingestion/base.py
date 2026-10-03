"""Repository loader abstract base class."""

from abc import ABC, abstractmethod

from app.models.entities import RepositoryInfo, SourceFile


class RepositoryLoader(ABC):
    """Abstract interface for repository loaders."""

    @abstractmethod
    def load_repository(self, target_path: str) -> tuple[RepositoryInfo, list[SourceFile]]:
        """Load repository, gather metadata, and enumerate source code files.

        Args:
            target_path: Local path or remote repository URL.

        Returns:
            Tuple of RepositoryInfo metadata and list of SourceFile objects.
        """
