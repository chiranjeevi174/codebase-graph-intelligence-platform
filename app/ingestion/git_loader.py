"""Local Git repository loader implementation with .gitignore filtering."""

import os
import re
import subprocess
from pathlib import Path

import pathspec

from app.ingestion.base import RepositoryLoader
from app.models.entities import RepositoryInfo, SourceFile
from app.utils.exceptions import RepositoryIngestionError
from app.utils.logger import logger

DEFAULT_IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "coverage",
    ".idea",
    ".vscode",
    "egg-info",
}

IGNORED_EXTENSIONS = {
    ".env",
    ".pem",
    ".key",
    ".crt",
    ".cer",
    ".p12",
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".exe",
    ".bin",
    ".zip",
    ".tar",
    ".gz",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
}

SECRET_FILENAME_PATTERNS = [
    r"^\.env.*",
    r".*\.pem$",
    r".*\.key$",
    r"id_rsa.*",
]

MAX_FILE_SIZE_BYTES = 1_048_576  # 1MB limit for individual code files

from app.parsing.language import EXTENSION_MAP

SUPPORTED_EXTENSIONS = EXTENSION_MAP


class LocalGitLoader(RepositoryLoader):
    """Loader for local repositories with pathspec-based .gitignore evaluation."""

    def __init__(self, default_ignored_dirs: set | None = None):
        self.ignored_dirs = default_ignored_dirs or DEFAULT_IGNORED_DIRS

    def _load_gitignore_spec(self, repo_root: Path) -> pathspec.PathSpec | None:
        """Load .gitignore if present in repository root."""
        gitignore_path = repo_root / ".gitignore"
        if gitignore_path.is_file():
            try:
                with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                    patterns = f.read().splitlines()
                return pathspec.PathSpec.from_lines("gitignore", patterns)
            except (OSError, Exception) as e:  # noqa: BLE001 — Safe .gitignore parsing fallback
                logger.warning(f"Failed to parse .gitignore at {gitignore_path}: {e}")
        return None

    def _get_git_commit_hash(self, repo_root: Path) -> str | None:
        """Attempt to extract git commit hash using git command line."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except (OSError, subprocess.SubprocessError) as e:
            logger.debug(f"Could not retrieve git commit hash for {repo_root}: {e}")
        return None

    def load_repository(self, target_path: str) -> tuple[RepositoryInfo, list[SourceFile]]:
        """Scans local path, enumerates files, filters ignores, and produces metadata."""
        repo_path = Path(target_path).resolve()
        if not repo_path.exists() or not repo_path.is_dir():
            raise RepositoryIngestionError(
                f"Target repository path does not exist or is not a directory: {target_path}"
            )

        repo_name = repo_path.name
        repo_id = repo_name.lower().replace(" ", "_").replace("-", "_")

        spec = self._load_gitignore_spec(repo_path)
        commit_hash = self._get_git_commit_hash(repo_path)

        source_files: list[SourceFile] = []
        languages_found = set()
        language_stats: dict[str, int] = {}

        for root, dirs, files in os.walk(repo_path):
            # Prune default ignored directories in-place
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]

            current_root = Path(root)
            rel_root = current_root.relative_to(repo_path)

            for file in files:
                rel_file_path = rel_root / file if str(rel_root) != "." else Path(file)
                rel_str = str(rel_file_path).replace("\\", "/")

                # Check secret patterns & ignored extensions
                if any(re.match(pattern, file, re.IGNORECASE) for pattern in SECRET_FILENAME_PATTERNS):
                    continue

                full_path = current_root / file
                ext = full_path.suffix.lower()

                if ext in IGNORED_EXTENSIONS:
                    continue

                # Check gitignore spec
                if spec and spec.match_file(rel_str):
                    continue

                if ext in SUPPORTED_EXTENSIONS:
                    language = SUPPORTED_EXTENSIONS[ext]

                    try:
                        size_bytes = full_path.stat().st_size
                        if size_bytes > MAX_FILE_SIZE_BYTES:
                            logger.warning(
                                f"Skipping file {rel_str}: size ({size_bytes} bytes) exceeds maximum limit ({MAX_FILE_SIZE_BYTES} bytes)"
                            )
                            continue

                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines = len(f.readlines())
                    except (OSError, Exception) as e:  # noqa: BLE001 — Safe file stats reading fallback
                        logger.warning(f"Failed to read stats for {full_path}: {e}")
                        lines = 0
                        size_bytes = 0

                    languages_found.add(language)
                    language_stats[language] = language_stats.get(language, 0) + 1

                    source_file = SourceFile(
                        file_path=str(full_path).replace("\\", "/"),
                        relative_path=rel_str,
                        language=language,
                        size_bytes=size_bytes,
                        lines_of_code=lines,
                        extension=ext,
                    )
                    source_files.append(source_file)

        repo_info = RepositoryInfo(
            repository_id=repo_id,
            name=repo_name,
            source="local",
            local_path=str(repo_path).replace("\\", "/"),
            path=str(repo_path).replace("\\", "/"),
            commit_hash=commit_hash,
            branch="main",
            default_branch="main",
            file_count=len(source_files),
            total_files=len(source_files),
            languages=list(languages_found),
            language_statistics=language_stats,
        )

        logger.info(f"Loaded repository '{repo_name}' with {len(source_files)} source files.")
        return repo_info, source_files
