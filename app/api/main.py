"""FastAPI Application Main Factory and Endpoint Setup."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pathlib import Path
from fastapi.staticfiles import StaticFiles

from app.api.routes import analysis, graph, health, ingestion, jobs, query, source, webhooks
from app.config.settings import get_settings
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    settings = get_settings()
    logger.info(
        f"Starting {settings.APP_NAME} (Environment: {settings.ENVIRONMENT}, LLM Provider: {settings.LLM_PROVIDER})..."
    )
    yield


def create_app() -> FastAPI:
    """Create and configure FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        description="Production-grade Graph RAG Codebase Graph Intelligence Platform",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Add Production Hardening Middleware
    from app.api.middleware import ProductionHardeningMiddleware
    app.add_middleware(ProductionHardeningMiddleware)

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API Routers
    app.include_router(health.router)
    app.include_router(ingestion.router)
    app.include_router(query.router)
    app.include_router(graph.router)
    app.include_router(analysis.router)
    app.include_router(jobs.router)
    app.include_router(source.router)
    app.include_router(webhooks.router)

    # Mount static frontend directory if present
    frontend_dir = Path("frontend")
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app


app = create_app()
