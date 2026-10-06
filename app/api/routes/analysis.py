"""Code Impact Analysis API endpoints."""

from fastapi import APIRouter, HTTPException

from app.analysis.impact_service import CodeImpactAnalysisService
from app.models.entities import ImpactAnalysisRequest, ImpactAnalysisResult

router = APIRouter(tags=["Analysis"])


from typing import Any
from pydantic import BaseModel, Field

from app.graph.graph_queries import GraphQueryManager


class ApiFlowAnalysisRequest(BaseModel):
    repository_id: str | None = Field(None, description="Optional target repository ID")
    path_or_symbol: str = Field(..., description="API path template, concrete URL, or client/endpoint symbol")
    max_hops: int = Field(3, description="Maximum graph traversal depth")


class ApiFlowAnalysisResponse(BaseModel):
    query_term: str
    paths_found: int
    paths: list[dict[str, Any]]


@router.post("/analysis/impact", response_model=ImpactAnalysisResult)
def analyze_code_impact(request: ImpactAnalysisRequest):
    """Analyze static code impact, dependency propagation, and affected files for a symbol modification."""
    try:
        service = CodeImpactAnalysisService()
        result = service.analyze_impact(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Code impact analysis failed: {e}")


@router.post("/analysis/api-flow", response_model=ApiFlowAnalysisResponse)
def analyze_api_flow(request: ApiFlowAnalysisRequest):
    """Analyze cross-language API flow connecting client calls, endpoints, and OpenAPI contracts."""
    try:
        qm = GraphQueryManager()
        raw_paths = qm.find_api_flow(
            identifier=request.path_or_symbol,
            max_hops=request.max_hops,
            repository_id=request.repository_id,
        )
        return ApiFlowAnalysisResponse(
            query_term=request.path_or_symbol,
            paths_found=len(raw_paths),
            paths=raw_paths,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"API flow analysis failed: {e}")


from app.diff.diff_analyzer import StructuralDiffAnalyzer
from app.diff.diff_models import ChangeImpactResult, DiffRequest


@router.post("/analysis/diff", response_model=ChangeImpactResult)
def analyze_structural_diff(request: DiffRequest):
    """Analyze structural Git diff, symbol changes, signature changes, and affected graph components."""
    try:
        analyzer = StructuralDiffAnalyzer()
        result = analyzer.analyze_diff(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Structural diff analysis failed: {e}")


from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.jobs.models import PRJobRequest
from app.jobs.service import JobService
from app.pr.models import PRAnalysisRequest, PRAnalysisResult
from app.pr.service import PRAnalysisService


@router.post("/analysis/pr")
async def analyze_pull_request(
    request: PRAnalysisRequest,
    wait: bool = Query(False, description="Whether to wait synchronously for PR analysis completion (default: False)"),
):
    """Analyze Pull/Merge Request. Default mode is asynchronous queue submission (HTTP 202). Set wait=true for synchronous execution."""
    try:
        if wait:
            service = PRAnalysisService()
            result = service.analyze_pr(request)
            return result

        job_req = PRJobRequest(
            provider=request.provider,
            repository=request.repository,
            pr_number=request.pr_number,
            base_ref=request.base_ref,
            target_ref=request.target_ref,
            repo_path=request.repo_path,
            dry_run=request.dry_run,
            max_hops=request.max_hops,
            wait=False,
        )
        service = JobService()
        job = await service.submit_pr_job(job_req)
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=job.model_dump(mode="json"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PR analysis failed: {e}")


from app.jobs.models import PRAnalysisRun
from app.jobs.repository import JobRepository


@router.get("/analysis/pr/{provider}/{repository:path}/{pr_number}/history", response_model=list[PRAnalysisRun])
def get_pr_analysis_history(
    provider: str,
    repository: str,
    pr_number: int,
    limit: int = Query(20, description="Maximum historical analysis runs to return"),
):
    """Retrieve historical PR analysis runs for specified provider, repository, and PR number."""
    try:
        repo_db = JobRepository()
        return repo_db.get_pr_history(provider=provider, repository=repository, pr_number=pr_number, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch PR history: {e}")



