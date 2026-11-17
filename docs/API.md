# API Documentation — Codebase Graph Intelligence Platform

This document describes the API endpoints provided by the **Codebase Graph Intelligence Platform**. The platform provides six primary user-facing intelligence features:
1. **Codebase Query (Graph RAG)**
2. **Impact Analysis**
3. **API Flow Analysis**
4. **Pull Request Analysis (Evidence-Based Review)**
5. **Architecture Intelligence & Visualization**
6. **Code Quality & Security Analysis**

---

## 1. Base Endpoints & Observability

| Method | Endpoint | Description | Response Status |
|--------|----------|-------------|-----------------|
| `GET` | `/live` | Liveness probe checking process existence | 200 OK |
| `GET` | `/ready` | Readiness probe checking Neo4j, Qdrant, and Redis connectivity | 200 OK / 503 Unavailable |
| `GET` | `/health` | Comprehensive system diagnostic and database status | 200 OK |
| `GET` | `/metrics` | Application request, error, and latency metrics summary | 200 OK |

---

## 2. Ingestion & Graph Exploration

| Method | Endpoint | Description | Response Status |
|--------|----------|-------------|-----------------|
| `POST` | `/ingest` | Ingest local repository into Neo4j Knowledge Graph & Qdrant vector database | 200 OK |
| `GET` | `/graph/summary` | Retrieve code graph statistics (node counts, edge counts, language distribution) | 200 OK |
| `GET` | `/source` | Fetch source code content by relative file path | 200 OK / 404 Not Found |

---

## 3. Code Intelligence & Analysis Endpoints

### 3.1 Codebase Query (Graph RAG)
| Method | Endpoint | Description | Response Status |
|--------|----------|-------------|-----------------|
| `POST` | `/query` | Execute Graph RAG hybrid retrieval query combining Neo4j graph traversal and Qdrant semantic search | 200 OK |

**Request Body (`QueryRequest`):**
```json
{
  "query": "Where is the authentication middleware implemented and how does it validate tokens?",
  "top_k": 5
}
```

### 3.2 Impact Analysis
| Method | Endpoint | Description | Response Status |
|--------|----------|-------------|-----------------|
| `POST` | `/analysis/impact` | Analyze downstream blast radius and call hierarchies for a target symbol or file | 200 OK |

**Request Body (`ImpactRequest`):**
```json
{
  "symbol_name": "verify_token",
  "max_depth": 3,
  "file_path": "app/auth/security.py"
}
```

### 3.3 API Flow Analysis
| Method | Endpoint | Description | Response Status |
|--------|----------|-------------|-----------------|
| `POST` | `/analysis/api-flow` | Trace API client calls to backend endpoint definitions, route paths, and handlers | 200 OK |

**Request Body (`APIFlowRequest`):**
```json
{
  "repo_path": "."
}
```

### 3.4 Architecture Intelligence & Visualization (NEW)
| Method | Endpoint | Description | Response Status |
|--------|----------|-------------|-----------------|
| `POST` | `/analysis/architecture` | Extract system architecture, directory modules, architectural layers, entry points, and grounded explanation | 200 OK |

**Request Body (`ArchitectureAnalysisRequest`):**
```json
{
  "repo_path": "."
}
```

**Response Payload (`ArchitectureAnalysisResult`):**
```json
{
  "summary": {
    "total_modules": 8,
    "total_files": 42,
    "total_classes": 30,
    "total_functions": 115,
    "total_cross_module_connections": 64
  },
  "layers": [
    {
      "name": "Presentation / API",
      "modules": ["app.api"],
      "description": "HTTP API controllers, routers, and request handling",
      "node_count": 8
    },
    {
      "name": "Business Logic & Services",
      "modules": ["app.analysis", "app.diff", "app.pr", "app.workflows"],
      "description": "Core intelligence, analysis pipelines, and domain logic",
      "node_count": 18
    },
    {
      "name": "Persistence & Storage",
      "modules": ["app.graph", "app.vector"],
      "description": "Database access, knowledge graph queries, and vector stores",
      "node_count": 6
    },
    {
      "name": "Infrastructure & Core Utilities",
      "modules": ["app.core", "app.parsers"],
      "description": "Cross-cutting utilities, configuration, and AST parsers",
      "node_count": 10
    }
  ],
  "entry_points": ["app/main.py", "app/api/routes/analysis.py"],
  "nodes": [...],
  "edges": [...],
  "explanation": "..."
}
```

### 3.5 Code Quality & Security Analysis (NEW)
| Method | Endpoint | Description | Response Status |
|--------|----------|-------------|-----------------|
| `POST` | `/analysis/quality-security` | Run static code quality checks, AST code smell analysis, and credential/secret scanning | 200 OK |

**Request Body (`QualitySecurityAnalysisRequest`):**
```json
{
  "repo_path": "."
}
```

**Response Payload (`QualitySecurityAnalysisResult`):**
```json
{
  "summary": {
    "total_findings": 7,
    "critical_count": 1,
    "high_count": 2,
    "medium_count": 3,
    "low_count": 1,
    "quality_findings_count": 4,
    "security_findings_count": 3
  },
  "findings": [
    {
      "id": "SEC-001",
      "title": "Hardcoded OpenAI API Key Detected",
      "category": "security",
      "severity": "critical",
      "file_path": "tests/test_credentials.py",
      "line_number": 14,
      "symbol_name": null,
      "code_evidence": "openai_key = \"sk-proj-****[REDACTED]****a1b2\"",
      "explanation": "A hardcoded API key or credential was discovered in source code.",
      "why_it_matters": "Committing credentials to version control risks complete credential compromise.",
      "recommended_action": "Revoke the credential immediately and migrate secrets to environment variables."
    }
  ],
  "explanation": "..."
}
```

> [!NOTE]
> All detected credentials are automatically redacted with cryptographic masks (e.g., `sk-proj-****[REDACTED]****a1b2`). Raw secret tokens are never written to logs or returned in API responses.

### 3.6 Internal Diff Engine (Excluded from OpenAPI Schema)
| Method | Endpoint | Description | Response Status |
|--------|----------|-------------|-----------------|
| `POST` | `/analysis/diff` | *Internal engine endpoint* powering PR Analysis. Hidden from public OpenAPI documentation (`include_in_schema=False`). | 200 OK |

---

## 4. Async Pull Request Analysis & Job Automation

| Method | Endpoint | Description | Response Status |
|--------|----------|-------------|-----------------|
| `POST` | `/analysis/pr` | Enqueue async evidence-based PR analysis job | 202 Accepted |
| `GET` | `/jobs` | List historical PR jobs (filterable by repository/status) | 200 OK |
| `GET` | `/jobs/{job_id}` | Retrieve job lifecycle status & worker metadata | 200 OK / 404 Not Found |
| `GET` | `/jobs/{job_id}/events` | SSE stream for real-time job state transitions | 200 OK (text/event-stream) |
| `GET` | `/jobs/{job_id}/result` | Fetch completed PR analysis report payload | 200 OK / 404 Not Found |
| `POST` | `/jobs/{job_id}/retry` | Manually retry FAILED or DEAD_LETTER job | 200 OK / 400 Bad Request |
| `GET` | `/analysis/pr/{provider}/{repository}/{pr_number}/history` | Retrieve historical PR runs | 200 OK |
| `POST` | `/webhooks/github` | Receive & authenticate GitHub PR webhook events | 202 Accepted / 401 Unauthorized |
| `POST` | `/webhooks/gitlab` | Receive & authenticate GitLab MR webhook events | 202 Accepted / 401 Unauthorized |

