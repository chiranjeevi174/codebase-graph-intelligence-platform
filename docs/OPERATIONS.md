# Operational Runbook — Codebase Graph Intelligence Platform

## Troubleshooting & Incident Response

### 1. Redis Connection Failures
- **Symptom**: `[JobRepository] Production environment requires operational Redis`.
- **Diagnostic**: Check `docker compose ps codebase_redis` and `redis-cli ping`.
- **Resolution**: Restart Redis container `docker compose restart redis`.

### 2. Stuck / Dead-Letter Jobs
- **Symptom**: Job status transitions to `DEAD_LETTER` with `attempt=3`.
- **Diagnostic**: Inspect status via `GET /jobs/{job_id}`. Read error classification in response.
- **Resolution**: Fix downstream dependency issues and trigger retry via `POST /jobs/{job_id}/retry`.

### 3. Neo4j / Qdrant Database Unavailability
- **Symptom**: Readiness probe `GET /ready` returns HTTP 530 Service Unavailable.
- **Diagnostic**: Check database container health `docker compose ps`.
- **Resolution**: Verify port exposure and container resource memory limits.

### 4. Webhook Authentication Failures
- **Symptom**: Webhook endpoints return `HTTP 401 Unauthorized`.
- **Diagnostic**: Verify `GITHUB_WEBHOOK_SECRET` or `GITLAB_WEBHOOK_SECRET` matches platform configuration.
