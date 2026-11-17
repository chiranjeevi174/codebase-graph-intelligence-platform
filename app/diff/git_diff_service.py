"""Service layer for low-level Git metadata and diff extraction."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.diff.diff_models import ChangeType, FileChange
from app.parsing.language import detect_language
from app.utils.logger import logger


class GitError(RuntimeError):
    """Base exception for Git operations."""


class RepositoryNotFoundError(GitError):
    """Raised when repository directory is missing or not a git repository."""


class GitRevisionNotFoundError(GitError):
    """Raised when a git revision does not exist locally and cannot be fetched."""


class GitDiffError(GitError):
    """Raised when git diff execution fails."""


def resolve_repository_path(repository: str | None = None, repo_path: str | None = None) -> Path:
    """Intelligently resolve local repository path across explicit paths, data/repositories, and fixtures.

    Search priority:
    1. Explicit non-default repo_path if it exists on disk and is a verified git repo directory.
    2. Ingested repositories in 'data/repositories/<repo_id>' or 'data/repositories/<repo_name>'.
    3. Test fixtures in 'tests/fixtures/<repo_name>'.
    4. Explicit repo_path if it exists on disk.
    5. Current working directory if inside a git work tree.
    """
    clean_repo_path = repo_path.strip() if repo_path else ""

    # 1. If explicit non-current-dir repo_path provided and exists with .git
    if clean_repo_path and clean_repo_path not in (".", "./"):
        candidate = Path(clean_repo_path).resolve()
        if (
            candidate.exists()
            and candidate.is_dir()
            and ((candidate / ".git").exists() or _is_inside_git_dir(candidate))
        ):
            return candidate

    # 2. Check data/repositories/
    if repository and repository.strip():
        raw_name = repository.strip().rstrip("/").removesuffix(".git")
        short_name = raw_name.split("/")[-1]
        slug_name = short_name.lower().replace(" ", "_").replace("-", "_")

        for cand_dir in [slug_name, short_name, raw_name]:
            p = Path("data/repositories") / cand_dir
            if p.exists() and p.is_dir():
                return p.resolve()

        # 3. Check tests/fixtures/
        for cand_dir in [short_name, slug_name]:
            p = Path("tests/fixtures") / cand_dir
            if p.exists() and p.is_dir():
                return p.resolve()

    # 4. Fall back to provided repo_path if it exists
    if clean_repo_path:
        p = Path(clean_repo_path).resolve()
        if p.exists() and p.is_dir():
            return p

    # 5. Fall back to current working directory
    return Path.cwd()


def _is_inside_git_dir(path: Path) -> bool:
    """Check if given path is inside a git working tree."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(path),
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode == 0 and res.stdout.strip().lower() == "true"
    except Exception:  # noqa: BLE001
        return False


class GitDiffService:
    """Interacts with local Git repository to extract commit SHAs, file diffs, and file content snapshots."""

    def __init__(self, repo_path: str | Path = ".", repository: str | None = None):
        self.repo_path = resolve_repository_path(repository=repository, repo_path=str(repo_path) if repo_path else None)

    def _run_git(self, args: list[str]) -> str:
        """Execute a git command within the repo directory without code execution."""
        if not self.repo_path.exists() or not self.repo_path.is_dir():
            raise RepositoryNotFoundError(f"Repository directory does not exist: {self.repo_path}")

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
            cmd_str = f"git {' '.join(args)}"
            logger.warning(f"[GitDiffService] Git command failed: {cmd_str}: {e.stderr.strip()}")
            raise GitDiffError(
                f"Git command failed (exit code {e.returncode}): {cmd_str}. Error: {e.stderr.strip()}"
            ) from e
        except OSError as e:
            logger.warning(f"[GitDiffService] OS error executing git in {self.repo_path}: {e}")
            raise RepositoryNotFoundError(f"Failed to execute git in {self.repo_path}: {e}") from e

    def is_git_repo(self) -> bool:
        """Check if target directory is a valid git repository."""
        return _is_inside_git_dir(self.repo_path)

    def has_commit(self, ref: str) -> bool:
        """Check if a specific commit / ref exists in the local Git object database."""
        if not ref or not ref.strip():
            return False
        clean_ref = ref.strip()
        try:
            self._run_git(["cat-file", "-e", f"{clean_ref}^{{commit}}"])
            return True
        except Exception:  # noqa: BLE001
            return False

    def resolve_ref(self, ref: str) -> str:
        """Resolve a Git reference (branch, tag, HEAD~1) to a full commit SHA."""
        clean_ref = ref.strip()
        try:
            return self._run_git(["rev-parse", "--verify", clean_ref])
        except Exception:  # noqa: BLE001 — Safe git ref resolution fallback
            try:
                return self._run_git(["rev-parse", clean_ref])
            except Exception:  # noqa: BLE001
                # Fallback if ref is already a 40-char SHA or placeholder
                return clean_ref

    def get_remote_url(self, remote: str = "origin") -> str | None:
        """Retrieve the configured remote URL."""
        try:
            url = self._run_git(["remote", "get-url", remote])
            return url.strip() if url else None
        except Exception:  # noqa: BLE001
            return None

    def fetch_remote(
        self,
        ref: str | None = None,
        pr_number: int | None = None,
        provider: str = "github",
        remote: str = "origin",
    ) -> bool:
        """Attempt to fetch ref or PR ref from remote git repository."""
        try:
            remotes = self._run_git(["remote"]).splitlines()
        except Exception:  # noqa: BLE001
            return False

        if not remotes:
            logger.warning(f"[GitDiffService] No remote configured in {self.repo_path}.")
            return False

        target_remote = remote if remote in remotes else remotes[0]
        fetched = False

        # 1. If PR number provided, fetch provider-specific PR ref
        if pr_number:
            refspec = None
            if provider.lower() == "github":
                refspec = f"pull/{pr_number}/head"
            elif provider.lower() == "gitlab":
                refspec = f"merge-requests/{pr_number}/head"

            if refspec:
                try:
                    logger.info(f"[GitDiffService] Fetching PR ref '{refspec}' from remote '{target_remote}'...")
                    self._run_git(["fetch", target_remote, refspec])
                    fetched = True
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"[GitDiffService] Fetching {refspec} from {target_remote} failed: {e}")

        # 2. If ref is provided and not present locally, fetch it directly
        if ref and not self.has_commit(ref):
            clean_ref = ref.strip()
            for fetch_target in [clean_ref, f"refs/heads/{clean_ref}"]:
                try:
                    logger.info(f"[GitDiffService] Fetching target '{fetch_target}' from remote '{target_remote}'...")
                    self._run_git(["fetch", target_remote, fetch_target])
                    fetched = True
                    if self.has_commit(clean_ref):
                        break
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"[GitDiffService] Fetching {fetch_target} failed: {e}")

        return fetched

    def ensure_ref(
        self,
        ref: str,
        pr_number: int | None = None,
        provider: str = "github",
    ) -> str:
        """Ensure a git reference is available locally, fetching from remote if necessary.

        Returns the resolved full 40-char commit SHA.
        Raises GitRevisionNotFoundError if the reference cannot be resolved or fetched.
        """
        clean_ref = ref.strip()

        # Check if already present locally
        if self.has_commit(clean_ref):
            resolved = self.resolve_ref(clean_ref)
            logger.info(f"[GitDiffService] Revision '{clean_ref}' is present locally ({resolved[:8]}).")
            return resolved

        # Not present locally; attempt remote fetch
        logger.info(
            f"[GitDiffService] Revision '{clean_ref}' not found locally in {self.repo_path}. Attempting remote fetch..."
        )
        self.fetch_remote(ref=clean_ref, pr_number=pr_number, provider=provider)

        # Check again after fetch
        if self.has_commit(clean_ref):
            resolved = self.resolve_ref(clean_ref)
            logger.info(f"[GitDiffService] Successfully resolved '{clean_ref}' -> {resolved} after remote fetch.")
            return resolved

        # Check FETCH_HEAD if ref matches or was fetched
        if self.has_commit("FETCH_HEAD"):
            fetch_head_sha = self.resolve_ref("FETCH_HEAD")
            if clean_ref in ("HEAD", fetch_head_sha) or (len(clean_ref) == 40 and fetch_head_sha.startswith(clean_ref)):
                logger.info(f"[GitDiffService] Using FETCH_HEAD ({fetch_head_sha[:8]}) for '{clean_ref}'.")
                return fetch_head_sha

        # Revision does not exist and could not be fetched
        err_msg = f"Git revision '{clean_ref}' does not exist locally in '{self.repo_path}' and could not be fetched from remote."
        logger.error(f"[GitDiffService] {err_msg}")
        raise GitRevisionNotFoundError(err_msg)

    def get_merge_base(self, base_ref: str, target_ref: str) -> str | None:
        """Compute merge-base (common ancestor) SHA between base_ref and target_ref."""
        try:
            out = self._run_git(["merge-base", base_ref, target_ref])
            mb = out.strip()
            return mb if mb else None
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[GitDiffService] Could not determine merge-base for {base_ref} and {target_ref}: {e}")
            return None

    def get_changed_files(
        self,
        base_ref: str,
        target_ref: str,
        repository_id: str = "default",
        pr_number: int | None = None,
        provider: str = "github",
        use_merge_base: bool = True,
    ) -> list[FileChange]:
        """Get list of changed files between base_ref and target_ref using git diff --name-status."""
        base_exists_before = self.has_commit(base_ref)
        target_exists_before = self.has_commit(target_ref)

        # 1. Resolve & ensure both revisions are available
        base_sha = self.ensure_ref(base_ref, pr_number=pr_number, provider=provider)
        target_sha = self.ensure_ref(target_ref, pr_number=pr_number, provider=provider)

        # 2. Determine merge-base comparison baseline for PR semantics
        diff_base = base_sha
        merge_base_sha = None
        if use_merge_base:
            merge_base_sha = self.get_merge_base(base_sha, target_sha)
            if merge_base_sha:
                diff_base = merge_base_sha

        # 3. Formulate git diff command
        diff_args = ["diff", "--name-status", "-M", diff_base, target_sha]
        diff_cmd_str = f"git diff --name-status -M {diff_base} {target_sha}"

        # 4. Diagnostic Logging (per requirements)
        logger.info(
            f"[GitDiffService:diff_execution] "
            f"repo_id='{repository_id}', repo_path='{self.repo_path}', pr_number={pr_number}, "
            f"base_ref='{base_ref}' (sha={base_sha}, existed_locally={base_exists_before}), "
            f"target_ref='{target_ref}' (sha={target_sha}, existed_locally={target_exists_before}), "
            f"merge_base='{merge_base_sha or 'none'}', "
            f"command='{diff_cmd_str}'"
        )

        try:
            output = self._run_git(diff_args)
            diff_exit_code = 0
        except GitDiffError as e:
            logger.error(f"[GitDiffService] Git diff failed: {e}")
            raise
        except Exception as e:
            logger.error(f"[GitDiffService] Unexpected error executing diff: {e}")
            raise GitDiffError(f"Git diff execution error: {e}") from e

        logger.info(f"[GitDiffService] Git diff command succeeded with exit code {diff_exit_code}.")

        # 5. Parse output into FileChange models
        file_changes: list[FileChange] = []
        raw_lines = [line.strip() for line in (output.splitlines() if output else []) if line.strip()]
        logger.info(f"[GitDiffService] Raw changed files detected from git diff: {len(raw_lines)}")

        for line in raw_lines:
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

        logger.info(f"[GitDiffService] Files retained after filtering/parsing: {len(file_changes)}")
        return file_changes

    def get_file_content_at_ref(self, ref: str, file_path: str) -> str | None:
        """Retrieve source code text for a specific file at a given Git reference."""
        try:
            return self._run_git(["show", f"{ref}:{file_path}"])
        except Exception as e:  # noqa: BLE001 — Safe fallback for file missing at git ref
            logger.debug(f"[GitDiffService] Could not retrieve {file_path} at {ref}: {e}")
            return None
