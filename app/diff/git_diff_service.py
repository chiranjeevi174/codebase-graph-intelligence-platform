"""Service layer for low-level Git metadata and diff extraction."""

import subprocess
from pathlib import Path

from app.diff.diff_models import ChangeType, FileChange
from app.parsing.language import detect_language
from app.utils.logger import logger


class GitDiffService:
    """Interacts with local Git repository to extract commit SHAs, file diffs, and file content snapshots."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()

    def _run_git(self, args: list[str]) -> str:
        """Execute a git command within the repo directory without code execution."""
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
                errors="replace",
            )
            return res.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.warning(f"[GitDiffService] Git command failed: git {' '.join(args)}: {e.stderr}")
            raise RuntimeError(f"Git command failed: git {' '.join(args)}. Error: {e.stderr.strip()}") from e

    def resolve_ref(self, ref: str) -> str:
        """Resolve a Git reference (branch, tag, HEAD~1) to a full commit SHA."""
        try:
            return self._run_git(["rev-parse", ref])
        except Exception:  # noqa: BLE001 — Safe git ref resolution fallback
            # Fallback if ref is already a 40-char SHA or invalid
            return ref

    def get_changed_files(self, base_ref: str, target_ref: str, repository_id: str = "default") -> list[FileChange]:
        """Get list of changed files between base_ref and target_ref using git diff --name-status."""
        base_sha = self.resolve_ref(base_ref)
        target_sha = self.resolve_ref(target_ref)

        # Use git diff with rename detection -M
        output = self._run_git(["diff", "--name-status", "-M", base_sha, target_sha])

        file_changes: list[FileChange] = []
        if not output:
            return file_changes

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) < 2:
                continue

            status_code = parts[0]

            if status_code.startswith("R"):
                # Rename: format is R100 old_path new_path
                old_path = parts[1]
                new_path = parts[2] if len(parts) > 2 else old_path
                status = ChangeType.RENAMED
                primary_path = new_path
            elif status_code == "A":
                old_path = None
                new_path = parts[1]
                status = ChangeType.ADDED
                primary_path = new_path
            elif status_code == "D":
                old_path = parts[1]
                new_path = None
                status = ChangeType.REMOVED
                primary_path = old_path
            else:  # M or others
                old_path = parts[1]
                new_path = parts[1]
                status = ChangeType.MODIFIED
                primary_path = parts[1]

            lang = detect_language(primary_path)

            file_changes.append(
                FileChange(
                    repository_id=repository_id,
                    file_path=primary_path,
                    old_path=old_path,
                    new_path=new_path,
                    status=status,
                    language=lang,
                    old_commit=base_sha,
                    new_commit=target_sha,
                )
            )

        return file_changes

    def get_file_content_at_ref(self, ref: str, file_path: str) -> str | None:
        """Retrieve source code text for a specific file at a given Git reference."""
        try:
            return self._run_git(["show", f"{ref}:{file_path}"])
        except Exception:  # noqa: BLE001 — Safe fallback for file missing at git ref
            # File might not exist at that ref (e.g. newly added or deleted)
            return None
