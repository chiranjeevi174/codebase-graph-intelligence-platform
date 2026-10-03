"""Command line interface for Codebase Graph Intelligence Platform."""

import uvicorn

from app.config.settings import get_settings
from app.utils.logger import logger


def main():
    """Start uvicorn FastAPI application server."""
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME} server on http://localhost:8000 ...")
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
