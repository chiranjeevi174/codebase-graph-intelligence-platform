"""Parses base and target source snapshots for structural AST/Tree-sitter comparison."""

from typing import NamedTuple

from app.diff.diff_models import FileChange
from app.diff.git_diff_service import GitDiffService
from app.models.entities import ExtractedCodeData, SourceFile
from app.parsing.parser_factory import ParserFactory
from app.utils.logger import logger


class FileSnapshotPair(NamedTuple):
    file_change: FileChange
    base_data: ExtractedCodeData | None
    target_data: ExtractedCodeData | None


class StructuralDiffExtractor:
    """Parses source code for modified/added/deleted files across base and target Git refs."""

    def __init__(self, git_service: GitDiffService | None = None):
        self.git_service = git_service or GitDiffService()

    def extract_file_snapshots(
        self,
        file_changes: list[FileChange],
        base_ref: str,
        target_ref: str,
        repository_id: str = "default",
    ) -> list[FileSnapshotPair]:
        """Parse source code snapshots for both base_ref and target_ref for each changed file."""
        snapshot_pairs: list[FileSnapshotPair] = []

        for fc in file_changes:
            # Base snapshot
            base_data: ExtractedCodeData | None = None
            if fc.old_path and fc.status != fc.status.ADDED:
                base_content = self.git_service.get_file_content_at_ref(base_ref, fc.old_path)
                if base_content is not None:
                    base_sf = SourceFile(
                        file_path=fc.old_path,
                        relative_path=fc.old_path,
                        language=fc.language,
                        size_bytes=len(base_content.encode("utf-8")),
                        lines_of_code=len(base_content.splitlines()),
                        extension=fc.old_path.split(".")[-1] if "." in fc.old_path else "",
                    )
                    try:
                        parser = ParserFactory.get_parser(fc.language)
                        base_data = parser.parse_file(base_sf, base_content, repository_id=repository_id)
                    except Exception as e:
                        logger.warning(f"[StructuralDiffExtractor] Failed parsing base ref {fc.old_path}: {e}")

            # Target snapshot
            target_data: ExtractedCodeData | None = None
            if fc.new_path and fc.status != fc.status.REMOVED:
                target_content = self.git_service.get_file_content_at_ref(target_ref, fc.new_path)
                if target_content is not None:
                    target_sf = SourceFile(
                        file_path=fc.new_path,
                        relative_path=fc.new_path,
                        language=fc.language,
                        size_bytes=len(target_content.encode("utf-8")),
                        lines_of_code=len(target_content.splitlines()),
                        extension=fc.new_path.split(".")[-1] if "." in fc.new_path else "",
                    )
                    try:
                        parser = ParserFactory.get_parser(fc.language)
                        target_data = parser.parse_file(target_sf, target_content, repository_id=repository_id)
                    except Exception as e:
                        logger.warning(f"[StructuralDiffExtractor] Failed parsing target ref {fc.new_path}: {e}")

            snapshot_pairs.append(
                FileSnapshotPair(
                    file_change=fc,
                    base_data=base_data,
                    target_data=target_data,
                )
            )

        return snapshot_pairs
