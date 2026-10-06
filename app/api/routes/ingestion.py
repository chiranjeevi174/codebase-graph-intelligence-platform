"""Repository ingestion endpoints delegating to RepositoryIngestionService."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ingestion.repository_service import RepositoryIngestionService
from app.models.entities import IngestionResult
from app.utils.logger import logger

router = APIRouter(prefix="/repositories", tags=["Ingestion"])


class IngestRequest(BaseModel):
    repository_path: str | None = Field(None, description="Local directory path to repository")
    repository_url: str | None = Field(None, description="Remote GitHub repository URL")
    branch: str | None = Field(None, description="Optional branch name if repository URL")
    force: bool = Field(False, description="Force re-cloning if remote target already exists")


# In-memory registry for ingested repos
_INGESTED_REPOS: list[IngestionResult] = []


@router.post("/ingest", response_model=IngestionResult)
def ingest_repository(request: IngestRequest):
    """Trigger complete end-to-end repository ingestion pipeline for a local path or GitHub URL."""
    target = request.repository_url or request.repository_path
    if not target:
        raise HTTPException(status_code=400, detail="Must provide either 'repository_path' or 'repository_url'.")

    service = RepositoryIngestionService()
    try:
        result = service.ingest_repository(target=target, branch=request.branch, force=request.force)
        # Store in registry if not present
        if not any(r.repository_id == result.repository_id for r in _INGESTED_REPOS):
            _INGESTED_REPOS.append(result)
        return result
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 # FastAPI 500 error boundary
        logger.error(f"Ingestion API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[IngestionResult])
def list_repositories():
    """List all ingested repositories and their ingestion statistics."""
    return _INGESTED_REPOS
