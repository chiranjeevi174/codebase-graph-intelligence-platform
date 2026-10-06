"""Source code retrieval endpoint for frontend source viewer."""

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.api.routes.ingestion import _INGESTED_REPOS

router = APIRouter(tags=["Source"])


@router.get("/source")
def get_source_code(
    file_path: str = Query(..., description="Target file path relative to repository or absolute path"),
    repository_id: str | None = Query(None, description="Optional repository ID context"),
):
    """Retrieve actual source code file contents for line-aware code viewing."""
    raw_path = file_path.strip().strip("'\"`")
    start_line = None
    end_line = None

    # Parse line suffixes like path.py:10-25 or path.py:10 or path.py#L10-L25
    line_match = re.search(r"[:#]L?(\d+)(?:-L?(\d+))?$", raw_path)
    if line_match:
        start_line = int(line_match.group(1))
        end_line = int(line_match.group(2)) if line_match.group(2) else start_line
        raw_path = raw_path[: line_match.start()]

    clean_path = raw_path.replace("\\", "/").lstrip("/")

    candidate_paths: list[Path] = [
        Path(clean_path),
    ]

    # Check registered ingested repositories
    for repo in _INGESTED_REPOS:
        if (not repository_id or repo.repository_id == repository_id) and repo.local_path:
            candidate_paths.append(Path(repo.local_path) / clean_path)

    if repository_id:
        candidate_paths.extend(
            [
                Path(f"data/repositories/{repository_id}") / clean_path,
                Path(f"tests/fixtures/{repository_id}") / clean_path,
                Path(f"tests/fixtures/{repository_id}") / clean_path.split("/", 1)[-1],
            ]
        )

    # Check standard fixture and repository directories
    candidate_paths.extend(
        [
            Path("tests/fixtures/sample_repo") / clean_path,
            Path("tests/fixtures/multi_language_repo") / clean_path,
            Path("tests/fixtures/diff_repo") / clean_path,
            Path("data/repositories") / clean_path,
            Path("tests") / clean_path,
            Path("app") / clean_path,
        ]
    )

    # If clean_path contains a prefix like "sample_repo/app/...", try stripping prefix
    if "/" in clean_path:
        sub_path = clean_path.split("/", 1)[1]
        candidate_paths.extend(
            [
                Path("tests/fixtures/sample_repo") / sub_path,
                Path("tests/fixtures/multi_language_repo") / sub_path,
                Path("tests/fixtures/diff_repo") / sub_path,
                Path("data/repositories") / sub_path,
            ]
        )

    target_file: Path | None = None
    for p in candidate_paths:
        try:
            if p.exists() and p.is_file():
                target_file = p.resolve()
                break
        except Exception:  # noqa: S112, BLE001 # Path check error boundary
            continue

    # Fallback search by filename if direct paths didn't match
    if not target_file:
        file_name = Path(clean_path).name
        search_dirs = [Path("tests/fixtures"), Path("data/repositories"), Path(".")]
        for s_dir in search_dirs:
            if s_dir.exists() and s_dir.is_dir():
                for found in s_dir.rglob(file_name):
                    if found.is_file() and not any(
                        part.startswith((".", "venv", "__pycache__")) for part in found.parts
                    ):
                        target_file = found.resolve()
                        break
            if target_file:
                break

    if not target_file:
        raise HTTPException(
            status_code=404,
            detail=f"Source file '{file_path}' could not be located in repository '{repository_id or 'default'}'.",
        )

    try:
        content = target_file.read_text(encoding="utf-8", errors="ignore")
        ext = target_file.suffix.lstrip(".").lower()
        lang_map = {
            "py": "python",
            "js": "javascript",
            "jsx": "javascript",
            "ts": "typescript",
            "tsx": "typescript",
            "go": "go",
            "java": "java",
            "json": "json",
            "md": "markdown",
            "html": "html",
            "css": "css",
            "yml": "yaml",
            "yaml": "yaml",
            "sql": "sql",
            "sh": "bash",
        }
        language = lang_map.get(ext, ext or "text")
        lines = content.splitlines()

        return {
            "file_path": file_path,
            "resolved_path": str(target_file),
            "repository_id": repository_id,
            "language": language,
            "line_count": len(lines),
            "content": content,
            "start_line": start_line,
            "end_line": end_line,
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 # FastAPI 500 error boundary
        raise HTTPException(status_code=500, detail=f"Failed reading source file: {e}")
