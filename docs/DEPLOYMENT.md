# Deployment Guide — Codebase Graph Intelligence Platform

## Production Deployment Architecture

Production deployments utilize containerized multi-service Docker Compose architecture.

### Production Environment Prerequisites
Set `ENVIRONMENT=production` in your production `.env` file:
```env
ENVIRONMENT="production"
LOG_FORMAT="json"
REDIS_URL="redis://codebase_redis:6379"
NEO4J_URI="bolt://codebase_neo4j:7687"
QDRANT_URL="http://codebase_qdrant:6333"
```

### Production Launch Command
```bash
docker compose up -d --build
```

### Infrastructure Health & Readiness Verification
- Liveness Probe: `curl -f http://localhost:8000/live`
- Readiness Probe: `curl -f http://localhost:8000/ready`
- Application Metrics: `curl -f http://localhost:8000/metrics`

### Multi-Worker Scaling
To scale worker instances horizontally:
```bash
docker compose up -d --scale worker=3
```
