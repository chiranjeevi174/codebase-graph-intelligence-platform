# API Documentation — Codebase Graph Intelligence Platform

## Base Endpoints & Observability

| Method | Endpoint | Description | Response Status |
|--------|----------|-------------|-----------------|
| `GET` | `/live` | Liveness probe checking process existence | 200 OK |
| `GET` | `/ready` | Readiness probe checking Neo4j, Qdrant, and Redis readiness | 200 OK / 530 Unavailable |
| `GET` | `/health` | Comprehensive system diagnostic and database status | 200 OK |
| `GET` | `/metrics` | Application request, error, and latency metrics summary | 200 OK |

## Graph RAG & Ingestion Endpoints

| Method | Endpoint | Description | Response Status |
|--------|----------|-------------|-----------------|
| `POST` | `/ingest` | Ingest local repository into Neo4j & Qdrant | 200 OK |
| `POST` | `/query` | Execute Graph RAG hybrid retrieval query | 200 OK |
| `GET` | `/graph/summary` | Retrieve code graph statistics (nodes, edges) | 200 OK |
| `GET` | `/source` | Fetch source code content by relative file path | 200 OK / 404 Not Found |

## Async PR Automation & Jobs Endpoints

| Method | Endpoint | Description | Response Status |
|--------|----------|-------------|-----------------|
| `POST` | `/analysis/pr` | Enqueue async PR analysis job | 202 Accepted |
| `GET` | `/jobs` | List historical PR jobs (filterable by repository/status) | 200 OK |
| `GET` | `/jobs/{job_id}` | Retrieve job lifecycle status & worker metadata | 200 OK / 404 Not Found |
| `GET` | `/jobs/{job_id}/events` | SSE stream for real-time job state transitions | 200 OK (text/event-stream) |
| `GET` | `/jobs/{job_id}/result` | Fetch completed PR analysis report payload | 200 OK / 404 Not Found |
| `POST` | `/jobs/{job_id}/retry` | Manually retry FAILED or DEAD_LETTER job | 200 OK / 400 Bad Request |
| `GET` | `/analysis/pr/{provider}/{repository}/{pr_number}/history` | Retrieve historical PR runs | 200 OK |
| `POST` | `/webhooks/github` | Receive & authenticate GitHub PR webhook events | 202 Accepted / 401 Unauthorized |
| `POST` | `/webhooks/gitlab` | Receive & authenticate GitLab MR webhook events | 202 Accepted / 401 Unauthorized |
