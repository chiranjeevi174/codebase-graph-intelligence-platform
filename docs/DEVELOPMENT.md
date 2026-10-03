# Development Guide — Codebase Graph Intelligence Platform

## Prerequisites
- Python >= 3.11
- `uv` package manager (`curl -sSf https://astral.sh/uv/install.sh | sh`)
- Docker Desktop (for Neo4j, Qdrant, and Redis services)

## Quick Start (Local Setup)

### 1. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 2. Infrastructure Services Setup
Launch Neo4j, Qdrant, and Redis via Docker Compose:
```bash
docker compose up -d neo4j qdrant redis
```

### 3. Install Dependencies & Virtual Environment
```bash
uv pip install -e .
uv pip install pytest pytest-asyncio ruff
```

### 4. Running Local API Server
```bash
uvicorn app.api.main:app --reload --port 8000
```

### 5. Running Local Background ARQ Worker
```bash
python scripts/worker.py
```

### 6. Executing Test Suite
```bash
uv run pytest tests/ -v
```
