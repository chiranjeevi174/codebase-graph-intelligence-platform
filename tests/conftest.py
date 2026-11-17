"""Pytest fixtures for unit and integration testing."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from app.config.settings import Settings
from app.utils.logger import logger


def _force_remove_readonly(func, path, exc_info):
    """Clear the readonly bit and reattempt file removal on Windows."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Failed to clear readonly permission on {path}: {e}")


@pytest.fixture(scope="session", autouse=True)
def setup_git_fixture_repos():
    """Ensure deterministic Git repositories exist in test fixtures for PR diff & job tests.

    Sets up:
    1. tests/fixtures/sample_repo with an explicit 'main' branch, two commits, and 'feature' branch.
    2. tests/fixtures/diff_repo with 'main' branch, Commit A (v1), Commit B (v2), and 'feature' branch.
    Cleans up isolated git metadata and temporary copied files on session teardown.
    """
    root_dir = Path(__file__).parent.parent
    sample_repo = root_dir / "tests" / "fixtures" / "sample_repo"
    diff_repo = root_dir / "tests" / "fixtures" / "diff_repo"

    created_sample_git = False
    created_diff_git = False
    diff_copied_files: list[Path] = []

    # 1. Setup sample_repo if .git is not present
    sample_git = sample_repo / ".git"
    if sample_repo.exists() and not sample_git.exists():
        try:
            subprocess.run(["git", "init", "-b", "main"], cwd=str(sample_repo), check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.name", "TestUser"], cwd=str(sample_repo), check=True, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=str(sample_repo),
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "add", "."], cwd=str(sample_repo), check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit on main"], cwd=str(sample_repo), check=True, capture_output=True
            )
            subprocess.run(["git", "branch", "-M", "main"], cwd=str(sample_repo), check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "--allow-empty", "-m", "Second commit on main"],
                cwd=str(sample_repo),
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "branch", "feature"], cwd=str(sample_repo), check=False, capture_output=True)
            created_sample_git = True
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Git fixture initialization skipped/failed for sample_repo: {e}")

    # 2. Setup diff_repo if .git is not present
    diff_git = diff_repo / ".git"
    if diff_repo.exists() and not diff_git.exists():
        v1_dir = diff_repo / "v1"
        v2_dir = diff_repo / "v2"
        if v1_dir.exists() and v2_dir.exists():
            try:
                subprocess.run(["git", "init", "-b", "main"], cwd=str(diff_repo), check=True, capture_output=True)
                subprocess.run(
                    ["git", "config", "user.name", "TestUser"], cwd=str(diff_repo), check=True, capture_output=True
                )
                subprocess.run(
                    ["git", "config", "user.email", "test@example.com"],
                    cwd=str(diff_repo),
                    check=True,
                    capture_output=True,
                )

                # Commit v1 files
                for f in v1_dir.glob("*"):
                    if f.is_file():
                        dest = diff_repo / f.name
                        shutil.copy(f, dest)
                        diff_copied_files.append(dest)

                subprocess.run(["git", "add", "."], cwd=str(diff_repo), check=True, capture_output=True)
                subprocess.run(
                    ["git", "commit", "-m", "Commit A (v1) on main"],
                    cwd=str(diff_repo),
                    check=True,
                    capture_output=True,
                )
                subprocess.run(["git", "branch", "-M", "main"], cwd=str(diff_repo), check=True, capture_output=True)

                # Commit v2 files
                for f in v2_dir.glob("*"):
                    if f.is_file():
                        dest = diff_repo / f.name
                        shutil.copy(f, dest)
                        if dest not in diff_copied_files:
                            diff_copied_files.append(dest)

                subprocess.run(["git", "add", "."], cwd=str(diff_repo), check=True, capture_output=True)
                subprocess.run(
                    ["git", "commit", "-m", "Commit B (v2) on main"],
                    cwd=str(diff_repo),
                    check=True,
                    capture_output=True,
                )
                subprocess.run(["git", "branch", "feature"], cwd=str(diff_repo), check=False, capture_output=True)
                created_diff_git = True
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Git fixture initialization skipped/failed for diff_repo: {e}")

    try:
        yield
    finally:
        # Teardown: clean up diff_repo copied files and git directories
        for f in diff_copied_files:
            try:
                if f.exists():
                    f.unlink()
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Failed to unlink copied file {f}: {e}")

        if created_diff_git and diff_git.exists():
            try:
                shutil.rmtree(diff_git, onerror=_force_remove_readonly)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Failed to rmtree diff_git {diff_git}: {e}")

        if created_sample_git and sample_git.exists():
            try:
                shutil.rmtree(sample_git, onerror=_force_remove_readonly)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Failed to rmtree sample_git {sample_git}: {e}")


@pytest.fixture
def test_settings():
    """Return test settings override."""
    return Settings(
        APP_NAME="Test Graph Intelligence Platform",
        ENVIRONMENT="test",
        LLM_PROVIDER="openai",
        OPENAI_API_KEY="test_openai_key",
    )


@pytest.fixture
def sample_python_code():
    """Return a sample Python source code string for AST testing."""
    return '''"""Sample Module Docstring."""

import os
from typing import List

class BaseService:
    def __init__(self, name: str):
        self.name = name

    def get_status(self) -> str:
        return "active"

class UserService(BaseService):
    """User management service class."""

    def __init__(self, name: str, db_url: str):
        super().__init__(name)
        self.db_url = db_url

    @classmethod
    def create_default(cls) -> "UserService":
        return cls("DefaultUser", "sqlite:///:memory:")

    async def fetch_user(self, user_id: int) -> dict:
        status = self.get_status()
        return {"id": user_id, "status": status}

def calculate_tax(amount: float, rate: float = 0.1) -> float:
    """Calculate tax helper function."""
    return amount * rate
'''
