"""Source code retrieval endpoint for frontend source viewer."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["Source"])


@router.get("/source")
def get_source_code(
    file_path: str = Query(..., description="Target file path relative to repository or absolute path"),
    repository_id: str | None = Query(None, description="Optional repository ID context"),
):
    """Retrieve actual source code file contents for line-aware code viewing."""
    candidate_paths = [
        Path(file_path),
        Path("tests/fixtures/sample_repo") / file_path,
        Path("tests/fixtures/multi_language_repo") / file_path,
        Path("tests/fixtures/diff_repo") / file_path,
        Path("data/repositories") / file_path,
    ]
    if repository_id:
        candidate_paths.insert(1, Path(f"data/repositories/{repository_id}") / file_path)
        candidate_paths.insert(2, Path(f"tests/fixtures/{repository_id}") / file_path)

    target_file: Path | None = None
    for p in candidate_paths:
        if p.exists() and p.is_file():
            target_file = p
            break

    if not target_file:
        raise HTTPException(status_code=404, detail=f"Source file '{file_path}' not found.")

    try:
        content = target_file.read_text(encoding="utf-8", errors="ignore")
        ext = target_file.suffix.lstrip(".")
        lang_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "go": "go",
            "java": "java",
            "json": "json",
            "md": "markdown",
            "html": "html",
            "css": "css",
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
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed reading source file: {e}")
