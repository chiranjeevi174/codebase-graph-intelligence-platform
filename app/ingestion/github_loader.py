"""GitHub Repository Loader implementation for cloning and downloading remote repositories."""

import re
import shutil
import subprocess
from pathlib import Path

from app.ingestion.base import RepositoryLoader
from app.ingestion.git_loader import LocalGitLoader
from app.models.entities import RepositoryInfo, SourceFile
from app.utils.exceptions import RepositoryIngestionError
from app.utils.logger import logger


class GitHubRepositoryLoader(RepositoryLoader):
    """Loader for remote GitHub repositories using git clone or archive download."""

    def __init__(self, base_storage_dir: str = "data/repositories"):
        self.base_storage_dir = Path(base_storage_dir).resolve()
        self.base_storage_dir.mkdir(parents=True, exist_ok=True)
        self.local_loader = LocalGitLoader()

    @staticmethod
    def is_github_url(source: str) -> bool:
        """Check if source string is a GitHub URL."""
        return bool(re.match(r"^https?://(www\.)?github\.com/[^/]+/[^/]+", source.strip()))

    @staticmethod
    def extract_repo_name(url: str) -> str:
        """Extract repository name from GitHub URL."""
        clean_url = url.strip().rstrip("/")
        clean_url = clean_url.removesuffix(".git")
        parts = clean_url.split("/")
        return parts[-1] if parts else "github_repo"

    def load_repository(
        self, target_path: str, branch: str | None = None, force: bool = False
    ) -> tuple[RepositoryInfo, list[SourceFile]]:
        """Clone remote GitHub repository locally and scan source files."""
        if not self.is_github_url(target_path):
            raise RepositoryIngestionError(f"Provided path is not a valid GitHub URL: {target_path}")

        repo_name = self.extract_repo_name(target_path)
        repo_id = repo_name.lower().replace(" ", "_").replace("-", "_")
        dest_dir = self.base_storage_dir / repo_id

        if dest_dir.exists() and force:
            logger.info(f"Force re-cloning enabled. Removing existing directory: {dest_dir}")
            shutil.rmtree(dest_dir, ignore_errors=True)

        if not dest_dir.exists():
            logger.info(f"Cloning GitHub repository '{target_path}' into {dest_dir}...")
            cmd = ["git", "clone", "--depth", "1"]
            if branch:
                cmd.extend(["-b", branch])
            cmd.extend([target_path, str(dest_dir)])

            try:
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode != 0:
                    raise RepositoryIngestionError(f"Failed to clone GitHub repository: {res.stderr}")
            except RepositoryIngestionError:
                raise
            except Exception as e:  # noqa: BLE001 # External process clone error translation
                raise RepositoryIngestionError(f"Git clone error for {target_path}: {e}")
        else:
            logger.info(f"Using existing cloned repository at {dest_dir}")

        # Delegate file enumeration & gitignore filtering to LocalGitLoader
        repo_info, source_files = self.local_loader.load_repository(str(dest_dir))

        # Update metadata to reflect remote source
        repo_info.source = "github"
        repo_info.path = target_path
        repo_info.local_path = str(dest_dir).replace("\\", "/")
        if branch:
            repo_info.branch = branch

        return repo_info, source_files
