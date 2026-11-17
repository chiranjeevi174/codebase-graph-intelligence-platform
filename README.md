# Codebase Graph Intelligence Platform

> **A production-oriented software engineering intelligence platform that combines Knowledge Graphs, vector retrieval, AST-based code analysis, Graph RAG, hybrid retrieval, and LLM reasoning to understand large software repositories.**

The **Codebase Graph Intelligence Platform** transforms a source-code repository into a structured, queryable representation of the software system.

Instead of treating a repository as a collection of text files, the platform extracts **files, modules, classes, functions, methods, imports, inheritance relationships, function calls, API routes, and other structural relationships** into a **Software Knowledge Graph** backed by Neo4j.

At the same time, source-code content is embedded into a **Qdrant vector database**, enabling semantic retrieval.

These two representations complement each other:

* **Neo4j** answers structural questions about how the system is connected.
* **Qdrant** answers semantic questions about what the code means.
* **Hybrid retrieval and Reciprocal Rank Fusion (RRF)** combine retrieval signals.
* **LangGraph** orchestrates multi-step reasoning workflows.
* **OpenAI** provides production LLM reasoning and generation.
* **FastAPI** exposes the platform through APIs.
* **Redis + ARQ** support asynchronous repository/PR processing workflows.

The result is a system providing exactly six primary software engineering intelligence capabilities:
1. **Codebase Query (Graph RAG)**: Multi-hop natural-language code reasoning.
2. **Impact Analysis**: Dependency explosion and blast-radius exploration.
3. **API Flow Analysis**: Cross-language endpoint-to-client call tracing.
4. **Pull Request Analysis**: Evidence-based automated PR review powered by internal structural diffing.
5. **Architecture Intelligence & Visualization**: Interactive module graph, architectural layers, and grounded topology explanation.
6. **Code Quality & Security Analysis**: AST code smell detection and credential/secret scanning with automated token redaction.

---

## Why This Project?

Traditional "chat with your code" systems commonly rely on:

```text
Repository
    ↓
Text chunks
    ↓
Vector database
    ↓
LLM
    ↓
Answer
```

That approach can work for semantic questions, but it loses important structural information.

For example:

> "If I change this method, what parts of the application could be affected?"

A pure vector search system may retrieve code that looks semantically similar, but it does not inherently understand:

```text
Function A
   ↓ CALLS
Function B
   ↓ CALLS
Function C
   ↓ USED BY
API Endpoint
   ↓ IMPLEMENTED BY
Service Layer
```

This platform explicitly models those relationships.

### The architecture therefore combines two complementary views of a codebase:

```text
                    SOURCE REPOSITORY
                           │
                           ▼
                 Repository Ingestion
                           │
                           ▼
                 Language / AST Parsing
                       /         \
                      /           \
                     ▼             ▼
          Software Knowledge       Code Embeddings
              Graph                   │
                │                     │
                ▼                     ▼
              Neo4j                 Qdrant
                │                     │
                └─────────┬───────────┘
                          ▼
                 Hybrid Retrieval
                          │
                    RRF / Fusion
                          │
                          ▼
                 LangGraph Workflow
                          │
                          ▼
                  LLM Reasoning
                          │
                          ▼
                    Answer / Analysis
```

This makes the project closer to a **code intelligence platform** than a conventional document RAG chatbot.

---

# Key Capabilities

## 1. Repository Understanding

The platform ingests software repositories and builds structured representations of their contents.

The ingestion pipeline can identify:

* repositories
* source files
* modules
* classes
* functions
* methods
* imports
* inheritance relationships
* function/method calls
* API routes
* signatures
* source locations
* language information
* structural relationships

---

## 2. Software Knowledge Graph

The extracted repository structure is represented as a graph in **Neo4j**.

Example:

```text
Repository
    │
    ├── CONTAINS
    ▼
   File
    │
    ├── DEFINES
    ▼
  Class
    │
    ├── DEFINES
    ▼
 Method
    │
    └── CALLS
         ▼
      Method
```

This enables multi-hop structural reasoning that is difficult to perform reliably using vector similarity alone.

---

# 3. Semantic Code Retrieval

Source-code content is embedded using:

```text
BAAI/bge-small-en-v1.5
```

The embeddings are stored in **Qdrant**.

Semantic retrieval allows the system to answer questions such as:

* "Where is authentication implemented?"
* "Which components handle user registration?"
* "Find code related to database connection pooling."
* "Where is JWT validation performed?"

---

# 4. Hybrid Retrieval

The platform combines structural and semantic retrieval rather than depending on a single retrieval mechanism.

The retrieval architecture includes:

```text
Semantic Retrieval
        │
        ├──────────┐
        │          │
        ▼          ▼
 Graph Retrieval   Semantic Retrieval
        │          │
        └────┬─────┘
             ▼
        Result Fusion
             │
             ▼
             RRF
             │
             ▼
       Ranked Context
```

**Reciprocal Rank Fusion (RRF)** is used to combine ranked retrieval results.

This allows the system to benefit from both:

* structural relevance
* semantic relevance

---

# 5. Graph RAG Reasoning

The reasoning layer is orchestrated using **LangGraph** to execute stateful, multi-stage retrieval and validation workflows. Rather than treating code comprehension as a single retrieval-to-generation prompt, a user query moves through dynamic reasoning, retrieval fusion, and validation nodes:

```mermaid
flowchart TD
    UserQuery["User Codebase Query"] --> QueryAnalysis["Query Analysis Node<br/>(Classify Intent & Candidate Symbols)"]
    QueryAnalysis --> EntityResolution["Entity Resolution Node<br/>(Fuzzy & Graph Candidate Matching)"]
    
    EntityResolution --> DualRetrieval{"Dual Retrieval"}
    DualRetrieval -->|"Cypher Traversal"| GraphRetrieval["Graph Subgraph Retrieval<br/>(Neo4j)"]
    DualRetrieval -->|"Dense Vectors"| SemanticRetrieval["Semantic Retrieval<br/>(Qdrant & BAAI/bge-small-en-v1.5)"]
    
    GraphRetrieval --> Fusion["Retrieval Fusion & RRF"]
    SemanticRetrieval --> Fusion
    
    Fusion --> SubgraphBuild["Subgraph Construction Node"]
    SubgraphBuild --> ContextFusion["Context Compilation Node<br/>(Sources, Code Snippets, Paths)"]
    ContextFusion --> AnswerGen["Answer Generation Node<br/>(OpenAI LLM Provider)"]
    AnswerGen --> Validation["Groundedness Validation Node<br/>(AnswerValidator)"]
    Validation --> FinalResponse["Structured Evidence Response"]
```

### Graph RAG Workflow Stages:
1. **Query Analysis**: Identifies intent (e.g. `api_flow`, `endpoint`, `architecture`, `callers`, `codebase_overview`) and extracts candidate symbol identifiers.
2. **Entity Resolution**: Matches candidate terms against indexed Neo4j entities using qualified names, exact names, and fuzzy matching.
3. **Dual Retrieval & Reciprocal Rank Fusion (RRF)**: Combines graph paths from Neo4j with dense semantic matches from Qdrant, fusing them with standard reciprocal rank scoring:
   $$\text{RRF Score}(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
4. **Subgraph Construction**: Extracts connected subgraphs (up to 50 nodes and 100 edges) representing the active reasoning neighborhood.
5. **Context Compilation**: Formats retrieved source snippets, graph paths, and entity relationships into structured context for the LLM.
6. **Answer Generation**: Generates structured markdown answers formatted with:
   - Direct Answer
   - Technical Explanation & Execution Flow
   - Relevant Source Files & Code Symbols
   - Why It Matters & Operational Implications
   - Recommended Next Actions / Developer Guidance
7. **Answer Groundedness Validation**: Cross-checks all cited files and symbols against retrieved grounding context. Discrepancies produce non-blocking validation warnings to prevent ungrounded AI hallucinations.

---

# 6. Code Impact Analysis

The platform provides static blast-radius analysis to evaluate the downstream consequences of modifying a function, class, or module.

```text
Changed Function / Symbol
       │
       ▼
 Direct Callers (In-degree 1)
       │
       ▼
 Transitive Callers (Hops 2..N)
       │
       ▼
 Dependent Classes & Modules
       │
       ▼
 Downstream API Routes & Consumers
```

Key features:
* **Configurable Traversal Depth**: Evaluate blast radius across 1 to 5 hops (default 3 hops) from the target symbol.
* **Qualified Symbol Resolution**: Resolves target symbols via `EntityResolver` across file paths, classes, and namespaces.
* **Interactive Cytoscape Visualizer**: Renders the complete blast radius as an interactive dependency subgraph with node inspection.
* **AI-Grounded Blast Radius Explanation**: Synthesizes the downstream risks, potential regression areas, and test recommendations using actual graph evidence.

---

# 7. API Flow Analysis

The API Flow Analysis engine traces complete HTTP request flows from client invocations through backend routers, controllers, services, and database layers across languages.

Key capabilities:
* **Multilingual Endpoint Extraction**: Discovers FastAPI and Flask route decorators (e.g. `@app.post("/api/v1/incidents")`, `@router.get(...)`), HTTP methods, path templates, controller symbols, and request/response Pydantic models.
* **Client Call Matching**: Scans frontend TypeScript, JavaScript, Fetch, and Axios client calls, resolving URL templates and matching them to backend route definitions.
* **Natural-Language Query Translation**: Interprets complex developer questions (e.g. *"Trace the complete API request flow for POST /api/v1/incidents in AegisOps"*) using `QueryAnalyzer` to extract candidate routes, controllers, and services without fabricating absent steps.
* **Sequential Execution Flow**: Constructs step-by-step execution chains with explicit source file paths, line ranges, and relationship evidence.

---

# 8. Pull Request Analysis — Evidence-Based Review

The platform provides automated, evidence-based pull request review workflows. Rather than presenting a generic diff or sending raw unified diff text directly to an LLM, the PR review system investigates changed files, modified symbols, signature drifts, API contract modifications, and downstream blast radius using an internal structural diff engine (`app/diff/`).

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer / Webhook
    participant API as FastAPI (/analysis/pr)
    participant Redis as Redis Broker
    participant Worker as ARQ Worker (scripts/worker.py)
    participant Diff as Internal Diff Engine (app/diff/)
    participant Graph as Neo4j & Impact Service
    participant LLM as OpenAI Provider
    participant SSE as EventSource (/jobs/{id}/events)
    participant UI as Frontend Console

    Dev->>API: POST /analysis/pr (repo, pr_number, base, head)
    API->>Redis: Check Idempotency (deduplicate in-flight jobs)
    API->>Redis: Enqueue Job (status=QUEUED, HTTP 202)
    API-->>Dev: Return PRAnalysisJob (job_id=pr_job_xxx)
    UI->>SSE: Connect GET /jobs/{job_id}/events
    
    Worker->>Redis: Dequeue Job (status=RUNNING)
    Worker-->>SSE: Push status=RUNNING
    Worker->>Diff: git diff base...head (3-dot comparison)
    Worker->>Diff: AST Symbol Diff (functions, classes, methods)
    Worker->>Diff: Signature Drift & Route Diff Analysis
    Worker->>Graph: Downstream Blast Radius Impact Analysis
    Worker->>LLM: Formulate Grounded Review & Risk Assessment
    Worker->>Redis: Persist PRAnalysisResult & PRAnalysisRun
    Worker->>Redis: Update Job (status=COMPLETED)
    Worker-->>SSE: Push status=COMPLETED
    UI->>API: GET /jobs/{job_id}/result
    API-->>UI: Return Structured PR Analysis Report
```

### PR Analysis Architecture & Capabilities:
* **Three-Dot Git Comparison Semantics**: Uses `git diff --name-status -M base...head` (computing the common merge base) to analyze only changes introduced on the PR branch.
* **Remote Ref Auto-Fetching**: If a PR head SHA or branch is not present in the local clone, `GitDiffService` automatically fetches `refs/pull/{pr_number}/head` or the remote branch from GitHub or GitLab.
* **AST Symbol Differentiation**: Computes exact modified, added, and deleted code symbols (`Function`, `Class`, `Method`), explicitly filtering out container symbols (`MODULE`, `FILE`) to report accurate symbol metrics.
* **Signature Drift & API Contract Analysis**: Identifies added, removed, or reordered parameters, default value modifications, and HTTP route alterations.
* **Asynchronous Queueing with Redis & ARQ**: PR jobs execute asynchronously in background worker processes (`scripts/worker.py`), avoiding HTTP gateway timeouts on large diffs.
* **Active-Job Idempotency**: If an identical analysis request is submitted while a job is `QUEUED` or `RUNNING`, the active job is reused to prevent duplicate worker execution. Completed historical jobs do not block subsequent fresh analysis runs; passing `force=True` forces a new execution immediately.
* **Real-Time SSE Streaming & Polling Fallback**: The web UI connects to Server-Sent Events (`/jobs/{job_id}/events`) for live state transitions (`QUEUED` → `RUNNING` → `COMPLETED`/`FAILED`), with automatic client polling fallback (`/jobs/{job_id}`).
* **Deduplicated PR History**: Historical PR runs are persisted in Redis (`pr_history:{provider}:{repo}:{pr_number}`) and deduplicated by `analysis_run_id` preserving chronological recency.
* **Automated Platform Feedback**: Posts sticky review comments with collapsible sections and risk assessment markers to GitHub pull requests or GitLab merge requests (`dry_run=True` generates the report safely without posting).

---

# 9. Architecture Intelligence & Visualization

The platform extracts and visualizes high-level codebase architecture directly from the Neo4j Knowledge Graph (with filesystem AST fallback).

Key capabilities:
* **Architecture Discovery**: Extracts modules, packages, files, classes, and cross-module connections across the repository.
* **Architectural Layer Classification**: Automatically categorizes code into 4 distinct architectural tiers:
  1. **Presentation / API**: HTTP API controllers, routers, endpoints, and request handling.
  2. **Business Logic & Services**: Core intelligence, analysis pipelines, workflows, and domain logic.
  3. **Persistence & Storage**: Database clients, knowledge graph queries, and vector stores.
  4. **Infrastructure & Utilities**: Cross-cutting utilities, configuration, and AST parsers.
* **Entry Point Detection**: Discovers system entry points (e.g. `main.py`, server entry points, CLI handlers).
* **Interactive Visualization Canvas**: Powered by Cytoscape.js with pan, zoom, fit to view, neighborhood highlighting, and right-panel node inspection.
* **Grounded Architecture Narrative**: Synthesizes a technical overview explaining module responsibilities and system topology without fabricating absent layers.

---

# 10. Code Quality & Security Analysis

The platform features static code quality and security scanning powered by AST inspection and regex pattern matching:
* **AST Code Quality Smells**:
  - Cyclomatic complexity exceeding thresholds (> 10)
  - Excessive function length (> 50 lines)
  - Excessive parameters (> 6)
  - Mutable default arguments (`def func(items=[])`)
  - Wildcard imports (`from module import *`)
  - Silent bare exception suppression (`except: pass`)
* **Security Vulnerability Patterns**:
  - Dynamic code execution (`eval`, `exec`)
  - Command injection risks (`shell=True`, `os.system`, `subprocess.Popen`)
  - SQL injection patterns (raw string formatting in SQL queries)
  - Insecure SSL verification (`verify=False`)
* **Credential & Secret Scanner**:
  - Detects OpenAI API keys (`sk-proj-...`), AWS access keys (`AKIA...`), GitHub personal access tokens (`ghp_...`), private keys (`-----BEGIN PRIVATE KEY-----`), and hardcoded passwords.
* **Automated Secret Redaction**:
  - All detected credentials are cryptographically masked (e.g. `sk-proj-****[REDACTED]****a1b2`). Raw credentials are never exposed in reports, API responses, or logs.
* **Structured Findings UI**:
  - Findings include severity (Critical, High, Medium, Low), category tabs, file location, masked code snippet, explanation, "Why It Matters", and recommended developer remediation. Includes click-to-view source code modal via `GET /source`.

---

# 11. GitHub and GitLab Integration

The integration layer provides repository-provider abstractions for external source-control systems.

Supported integrations include:

* GitHub
* GitLab

The architecture separates provider-specific functionality from the core analysis system, making the platform easier to extend.

---

# 12. Asynchronous Job Processing

Repository and PR analysis can involve expensive operations such as:

* repository loading
* parsing
* graph construction
* embedding generation
* retrieval
* LLM reasoning
* diff analysis

The project therefore includes an asynchronous job architecture using:

```text
Redis
  +
ARQ Workers
  +
Job Repository
  +
Job Service
```

The job system includes production-oriented concerns such as:

* asynchronous processing
* job state tracking
* retries
* idempotency
* concurrency handling
* job history
* failure handling
* dead-letter handling

---

# 13. Multi-Language Code Analysis

The parsing layer is designed around language-specific parsers and shared parsing abstractions.

The repository contains parsers for:

* Python
* Java
* JavaScript
* TypeScript
* Go

The architecture separates:

```text
Language Detection
        │
        ▼
Parser Factory
        │
        ├── Python Parser
        ├── Java Parser
        ├── JavaScript Parser
        ├── TypeScript Parser
        └── Go Parser
```

This allows the platform to build a common software representation across different programming languages.

---

# System Architecture

```text
                         ┌─────────────────────────┐
                         │     Developer / API     │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │       FastAPI API       │
                         │  REST + Streaming/API   │
                         └────────────┬────────────┘
                                      │
                    ┌─────────────────┼──────────────────┐
                    │                 │                  │
                    ▼                 ▼                  ▼
             Repository           Query / RAG       PR / Webhook
             Ingestion             Analysis          Analysis
                    │                 │                  │
                    ▼                 │                  ▼
             Language Detection       │            Async Jobs
                    │                 │                  │
                    ▼                 │             Redis + ARQ
              AST / Parsing            │                  │
                    │                 │                  │
             ┌──────┴──────┐          │                  │
             │             │          │                  │
             ▼             ▼          │                  │
        Knowledge      Embeddings     │                  │
          Graph             │         │                  │
             │              │         │                  │
             ▼              ▼         │                  │
           Neo4j         Qdrant       │                  │
             │              │         │                  │
             └──────┬───────┘         │                  │
                    │                 │                  │
                    └────────┬────────┘                  │
                             ▼                           │
                     Hybrid Retrieval                   │
                             │                           │
                             ▼                           │
                          RRF / Fusion                   │
                             │                           │
                             ▼                           │
                     LangGraph Workflow                 │
                             │                           │
                             ▼                           │
                       OpenAI LLM                        │
                             │                           │
                             ▼                           │
                     Reasoned Analysis ◄────────────────┘
```

```mermaid
flowchart TD
    Client["Developer / UI / Webhook"] --> API["FastAPI Application Server"]
    
    subgraph CoreServices ["Core Intelligence Services"]
        API --> Ingestion["Repository Ingestion Engine"]
        API --> QueryEngine["Graph RAG Engine"]
        API --> ImpactService["Impact Analysis Service"]
        API --> APIFlowService["API Flow Analysis Service"]
        API --> ArchService["Architecture Intelligence"]
        API --> QualitySecurity["Quality & Security Scanner"]
        API --> PRService["PR Analysis & Webhook Handler"]
    end
    
    Ingestion --> AST["AST & Tree-sitter Parsers"]
    AST --> Neo4j[("Neo4j Knowledge Graph")]
    AST --> Embeddings["Hugging Face Embeddings<br/>BAAI/bge-small-en-v1.5"]
    Embeddings --> Qdrant[("Qdrant Vector DB")]
    
    QueryEngine --> LangGraph["LangGraph Workflow"]
    LangGraph --> Hybrid["Hybrid Retrieval & RRF"]
    Hybrid --> Neo4j
    Hybrid --> Qdrant
    LangGraph --> OpenAI["OpenAI LLM Provider"]
    LangGraph --> Validator["Answer Validator"]
    
    PRService --> RedisQueue[("Redis Queue")]
    RedisQueue --> ARQWorker["ARQ Background Worker (scripts/worker.py)"]
    ARQWorker --> DiffEngine["Internal Structural Diff Engine (app/diff/)"]
    ARQWorker --> ImpactService
    ARQWorker --> OpenAI
    ARQWorker --> PRHistory[("Job & PR History (Redis)")]
```

---

# Knowledge Graph Model

## Node Types

The graph represents software entities including:

| Node         | Purpose                         |
| ------------ | ------------------------------- |
| `Repository` | Root repository representation  |
| `File`       | Source file and metadata        |
| `Module`     | Module/namespace representation |
| `Class`      | Class definition                |
| `Function`   | Top-level function              |
| `Method`     | Class method                    |

## Relationship Types

Examples include:

```text
(:Repository)-[:CONTAINS]->(:File)

(:File)-[:DEFINES]->(:Class)

(:File)-[:DEFINES]->(:Function)

(:File)-[:DEFINES]->(:Module)

(:File)-[:IMPORTS]->(:Module)

(:Class)-[:INHERITS]->(:Class)

(:Class|Function|Method)-[:CALLS]->(:Function|Method)
```

Relationships can contain metadata such as:

* source file
* line number
* imported symbol
* alias
* qualified name
* relationship-specific information

This graph structure forms the foundation for structural code reasoning.

---

# Retrieval Architecture

The retrieval subsystem combines multiple signals.

```text
                   User Query
                       │
                       ▼
                Query Analysis
                       │
              ┌────────┴────────┐
              │                 │
              ▼                 ▼
        Graph Retrieval    Semantic Retrieval
              │                 │
              │              Qdrant
              │                 │
              └────────┬────────┘
                       ▼
                Result Fusion
                       │
                       ▼
             Reciprocal Rank Fusion
                       │
                       ▼
                Ranked Context
                       │
                       ▼
                LangGraph RAG
```

This is particularly useful because software questions frequently require both:

**Semantic understanding**

> "Find the code responsible for authentication."

and:

**Structural understanding**

> "Which functions call the authentication service?"

---

# LLM Architecture

The project uses an abstraction layer around LLM access.

```text
              Application / Workflow
                       │
                       ▼
                 get_llm()
                       │
                       ▼
              Base LLM Interface
                       │
                       ▼
              OpenAI Provider
                       │
                       ▼
                 OpenAI Model
```

The current production provider is:

```text
OpenAI
```

The LLM layer is intentionally separated from:

* graph storage
* vector storage
* embeddings
* retrieval
* repository parsing
* API routes

This keeps model invocation concerns isolated from the rest of the system.

### Current configuration

Set the provider in `.env`:

```ini
LLM_PROVIDER="openai"
OPENAI_MODEL="gpt-4o-mini"
OPENAI_API_KEY="your-key-here"
```

> **Security:** Never commit `.env`, API keys, tokens, passwords, or other credentials to Git.

---

# Technology Stack

| Layer | Technology | Version / Spec | Role |
| :--- | :--- | :--- | :--- |
| **Language** | Python | 3.11+ | Core implementation |
| **Package Management** | `uv` / pip | Latest | Environment and dependency synchronization |
| **API Framework** | FastAPI | >= 0.110.0 | High-performance asynchronous REST API, OpenAPI docs, and streaming |
| **ASGI Server** | Uvicorn | >= 0.28.0 | ASGI production application server with hot-reload support |
| **Workflow Engine** | LangGraph | >= 0.0.25 | Stateful graph-based multi-step reasoning and retrieval pipelines |
| **LLM Framework** | LangChain Core | >= 0.1.30 | Retrieval, prompt construction, and provider abstractions |
| **Production LLM** | OpenAI | `gpt-6-luna` / `gpt-4o-mini` | Code reasoning, review synthesis, and architecture explanation |
| **Embeddings** | Hugging Face | `sentence-transformers` | Local dense code embedding generation |
| **Embedding Model** | `BAAI/bge-small-en-v1.5` | 384 dimensions | Compact, state-of-the-art semantic code retrieval embeddings |
| **Vector Database** | Qdrant | 1.8.0+ / latest | Fast semantic vector index for code snippets and symbols |
| **Knowledge Graph** | Neo4j | 5 Community (APOC) | Graph database storing code nodes, calls, imports, and relationships |
| **Background Task Queue** | ARQ | >= 0.25.0 | Asynchronous job execution for long-running PR analysis workflows |
| **Queue Broker & Cache** | Redis | 7 Alpine | Distributed job state persistence, active idempotency, and SSE pub/sub |
| **AST & Code Parsing** | Python AST & Tree-sitter | `tree-sitter==0.21.3` | Multilingual syntax extraction (Python, Go, Java, JS, TS) |
| **Frontend UI** | HTML5, CSS3, JavaScript | ES6+ Vanilla | High-performance console styled in Midnight Graphite & Electric Blue |
| **Graph Visualization** | Cytoscape.js | 3.28.1 | Interactive client-side knowledge graph and blast radius explorer |
| **SCM Integrations** | Git, GitHub REST, GitLab API | Native / REST | Local repository resolution, remote fetch, and webhook authentication |
| **Automated Testing** | Pytest & pytest-asyncio | >= 8.0.0 | Comprehensive unit and integration test suites |
| **Static Code Quality** | Ruff | >= 0.3.0 | High-speed Python linter and code quality checker |
| **CI/CD Pipeline** | GitHub Actions | `.github/workflows/ci.yml` | Automated multi-OS build, linting, and regression test execution |
| **Containerization** | Docker & Docker Compose | Compose v2 | Local containerized orchestration for Neo4j, Qdrant, and Redis |

---

# Project Structure

```text
codebase-graph-intelligence-platform/
│
├── app/
│   ├── cli.py                         # CLI entrypoint for uvicorn application server
│   ├── __init__.py
│   │
│   ├── analysis/                      # Core intelligence and architectural services
│   │   ├── architecture_service.py    # Architectural layer, module, and entrypoint discovery
│   │   ├── impact_service.py          # Neo4j graph blast-radius and caller traversal
│   │   └── quality_security_service.py # AST code smell & secret/vulnerability scanner
│   │
│   ├── api/                           # FastAPI endpoints and HTTP middleware
│   │   ├── main.py                    # FastAPI application initialization & static routes
│   │   ├── middleware.py              # Request tracking, CORS, and error handling
│   │   └── routes/
│   │       ├── analysis.py            # Impact, API flow, architecture, and quality endpoints
│   │       ├── graph.py               # Graph inspection and summary endpoints
│   │       ├── health.py              # Health check, liveness, and readiness probes
│   │       ├── ingestion.py           # Repository ingestion trigger endpoint
│   │       ├── jobs.py                # Asynchronous PR job lifecycle & SSE streaming
│   │       ├── query.py               # Codebase Query (Graph RAG) endpoint
│   │       ├── source.py              # Safe source-code file retrieval endpoint
│   │       └── webhooks.py            # GitHub/GitLab webhook ingestion endpoints
│   │
│   ├── config/
│   │   └── settings.py                # Pydantic Settings and environment configuration
│   │
│   ├── diff/                          # Internal structural diff engines (powers PR Analysis)
│   │   ├── api_diff.py                # HTTP route and OpenAPI contract differences
│   │   ├── diff_analyzer.py           # Structural diff analyzer orchestrator
│   │   ├── diff_models.py             # Pydantic models for files, symbols, and signatures
│   │   ├── git_diff_service.py        # Low-level Git diff extraction, remote fetch, and merge-base
│   │   ├── relationship_diff.py       # Knowledge graph edge diffs
│   │   ├── signature_diff.py          # AST parameter, type, and return value drift analysis
│   │   ├── structural_diff.py         # Structural diff engine combining file and AST changes
│   │   └── symbol_diff.py             # Executable symbol changes (filtering container symbols)
│   │
│   ├── embeddings/                    # Vector embedding abstraction and storage
│   │   ├── embedder.py                # Embedding orchestration
│   │   ├── model.py                   # Hugging Face BAAI/bge-small-en-v1.5 wrapper
│   │   └── qdrant_store.py            # Qdrant client, collection creation, and upsert
│   │
│   ├── evaluation/                    # Platform evaluation framework
│   │   ├── answer_evaluator.py        # Answer completeness and citation evaluation
│   │   ├── dataset_loader.py          # Evaluation benchmark dataset loader
│   │   ├── evaluation_runner.py       # Benchmark test runner
│   │   ├── graph_evaluator.py         # Graph path accuracy evaluation
│   │   ├── latency_tracker.py         # Latency benchmarking
│   │   ├── metrics.py                 # Hit@K, MRR, Path Accuracy, Citation precision
│   │   ├── models.py                  # Evaluation schemas
│   │   ├── report_generator.py        # Markdown/JSON evaluation report generation
│   │   └── retrieval_evaluator.py     # Retrieval precision and recall metrics
│   │
│   ├── graph/                         # Neo4j knowledge graph interface
│   │   ├── graph_builder.py           # Graph node and edge ingestion pipeline
│   │   ├── graph_queries.py           # Cypher queries for impact, callers, and subgraphs
│   │   ├── neo4j_client.py            # Connection management and session pooling
│   │   ├── schema.py                  # Node labels, relationship types, and constraints
│   │   └── subgraph_builder.py        # Subgraph extraction for visualization and context
│   │
│   ├── ingestion/                     # Repository loaders and file discovery
│   │   ├── base.py                    # Ingestion interfaces and abstract loaders
│   │   ├── github_loader.py           # Remote GitHub repository cloning and metadata
│   │   ├── git_loader.py              # Git repository inspection and file enumerator
│   │   └── repository_service.py      # End-to-end repository indexing pipeline
│   │
│   ├── integrations/                  # Source code management provider integrations
│   │   ├── base.py                    # Provider abstraction interface
│   │   ├── factory.py                 # PR Provider factory (GitHub, GitLab)
│   │   ├── github.py                  # GitHub REST API client, PR metadata, and comments
│   │   └── gitlab.py                  # GitLab API client and MR discussions
│   │
│   ├── jobs/                          # Asynchronous job processing infrastructure
│   │   ├── models.py                  # PRAnalysisJob, PRAnalysisRun, and job status enums
│   │   ├── queue.py                   # ARQ job dispatch and Redis client pool
│   │   ├── repository.py              # Job state persistence and deduplicated PR history
│   │   ├── service.py                 # Job lifecycle orchestration and active-job idempotency
│   │   └── worker.py                  # ARQ worker tasks and job execution boundary
│   │
│   ├── llm/                           # LLM provider abstractions
│   │   ├── adapters.py                # Message formatting adapters
│   │   ├── base.py                    # Base LLM provider interface
│   │   ├── factory.py                 # LLM provider factory
│   │   └── openai_provider.py         # Production OpenAI provider implementation
│   │
│   ├── models/
│   │   └── entities.py                # Core domain entities, symbols, and search results
│   │
│   ├── parsing/                       # Multilingual AST and Tree-sitter code parsers
│   │   ├── api_extractor.py           # AST endpoint and client invocation extractor
│   │   ├── api_matcher.py             # Cross-language endpoint-to-client matching
│   │   ├── base.py                    # Base parser interface
│   │   ├── go_parser.py               # Tree-sitter Go parser
│   │   ├── javascript_parser.py       # Tree-sitter JavaScript parser
│   │   ├── java_parser.py             # Tree-sitter Java parser
│   │   ├── language.py                # File extension to language mapping
│   │   ├── models.py                  # Parsed entity data models
│   │   ├── parser_factory.py          # Language parser factory
│   │   ├── python_parser.py           # Python standard AST parser
│   │   ├── relationship_extractor.py  # Call and import relationship extraction
│   │   ├── tree_sitter_base.py        # Tree-sitter grammar loading utility
│   │   ├── typescript_parser.py       # Tree-sitter TypeScript parser
│   │   └── url_normalizer.py          # HTTP path and template normalization
│   │
│   ├── pr/                            # Pull Request analysis domain logic
│   │   ├── comment_formatter.py       # Markdown PR review comment generator with sticky markers
│   │   ├── models.py                  # PRAnalysisRequest, PRAnalysisResult, PRAnalysisSummary
│   │   ├── service.py                 # Core PR review analysis pipeline and diff coordinator
│   │   └── webhook_service.py         # Webhook signature verification and event parsing
│   │
│   ├── reasoning/                     # Retrieval reasoning and groundedness validation
│   │   ├── answer_validator.py        # Groundedness validation (preventing hallucinations)
│   │   ├── entity_resolver.py         # Entity name and qualified name resolver
│   │   └── query_analyzer.py          # Query intent and candidate symbol classifier
│   │
│   ├── retrieval/                     # Hybrid retrieval and context ranking
│   │   ├── context_fusion.py          # Context formatting for LLM prompt ingestion
│   │   ├── hybrid_retriever.py        # Combined graph and vector retrieval orchestrator
│   │   ├── rrf.py                     # Reciprocal Rank Fusion (RRF) algorithm
│   │   └── semantic_retriever.py      # Qdrant vector semantic search
│   │
│   ├── utils/
│   │   ├── exceptions.py              # Domain exceptions
│   │   └── logger.py                  # Structured console and file logging
│   │
│   └── workflows/
│       └── graph_rag.py               # LangGraph Graph RAG multi-step state graph
│
├── frontend/                          # Midnight Graphite developer intelligence console
│   ├── favicon.svg                    # Geometric brand favicon
│   ├── index.html                     # Single-page application console layout
│   ├── css/
│   │   └── styles.css                 # Midnight Graphite theme, grid layout, and card styling
│   └── js/
│       ├── api.js                     # Centralized API fetch wrapper and error handler
│       ├── architecture.js            # Architecture graph explorer and layer cards
│       ├── diff.js                    # Internal diff display helpers
│       ├── graph.js                   # Interactive Cytoscape.js canvas controller
│       ├── impact.js                  # Blast-radius explorer and caller graph handler
│       ├── pr.js                      # Asynchronous PR analysis submission, SSE, and history
│       ├── quality_security.js        # Code smell and masked secret findings table
│       ├── query.js                   # Graph RAG query submission and structured answer renderer
│       ├── state.js                   # Shared client-side reactive UI state
│       └── ui.js                      # View switching, tabs, toasts, and modal dialogs
│
├── scripts/                           # Operational scripts and worker entrypoints
│   ├── analyze_api_flow.py            # CLI script to test API flow analysis
│   ├── analyze_diff.py                # Internal verification script for structural diff engine
│   ├── analyze_impact.py              # CLI script to test impact analysis
│   ├── analyze_pr.py                  # CLI script to test PR analysis
│   ├── ingest_repository.py           # Ingestion CLI for local repositories
│   ├── run_evaluation.py              # Evaluation benchmark runner
│   ├── test_openai_smoke.py           # Smoke test verifying OpenAI provider connectivity
│   ├── verify_query_browser.mjs       # Headless browser verification script for frontend QA
│   └── worker.py                      # ARQ background worker entry point
│
├── tests/
│   ├── fixtures/                      # Test repositories (sample_repo, diff_repo, multi_language_repo)
│   ├── integration/                   # Live database integration tests
│   └── unit/                          # 134+ comprehensive unit and regression tests
│
├── docs/                              # Detailed technical documentation
│   ├── API.md                         # Complete API specification and payloads
│   ├── ARCHITECTURE.md                # System design and component interactions
│   ├── DEPLOYMENT.md                  # Docker and production deployment guide
│   ├── DEVELOPMENT.md                 # Contributor guide and environment setup
│   ├── EVALUATION.md                  # Benchmark dataset and evaluation metrics
│   └── OPERATIONS.md                  # Production monitoring, logging, and troubleshooting
│
├── .env.example                       # Documented environment variable template
├── docker-compose.yml                 # Local Docker orchestration for Neo4j, Qdrant, and Redis
├── pyproject.toml                     # Python package metadata and tool configs (Ruff, Pytest)
├── requirements.txt                   # Pip dependency manifest
├── uv.lock                            # Deterministic dependency lockfile
├── README.md                          # Primary platform documentation
└── .gitignore
```

---

# Local Development

## Prerequisites

Recommended local environment:

* Python 3.11
* `uv`
* Docker Desktop
* Git
* OpenAI API key
* sufficient local resources for the selected embedding model

Neo4j, Qdrant, and Redis are intended to run locally through Docker Compose.

---

# Installation

From Windows CMD:

```cmd
cd /d "D:\PROJECTS\CODEBASE GRAPH INTELLIGENCE PLATFORM"
```

Synchronize the Python environment:

```cmd
uv sync
```

Create your local environment file:

```cmd
copy .env.example .env
```

Then edit `.env` and configure the required services and OpenAI credentials.

---

# Start Infrastructure

Start the local infrastructure:

```cmd
docker-compose up -d
```

Verify the running containers:

```cmd
docker-compose ps
```

Expected infrastructure includes:

```text
Neo4j
Qdrant
Redis
```

Neo4j Browser:

```text
http://localhost:7474
```

Qdrant:

```text
http://localhost:6333
```

Neo4j Bolt:

```text
bolt://localhost:7687
```

---

# Start the API

Run the application using the project entry point:

```cmd
uv run codebase-graph-intelligence-platform
```

Or run Uvicorn directly:

```cmd
uv run uvicorn app.api.main:app --reload --port 8000
```

The API becomes available at:

```text
http://localhost:8000
```

Interactive API documentation:

```text
http://localhost:8000/docs
```

Alternative API documentation:

```text
http://localhost:8000/redoc
```

---

# Start the ARQ Background Worker

The platform relies on an **asynchronous worker process** powered by **Redis and ARQ** to execute background tasks, specifically Pull Request Analysis (fetching git diffs, computing AST symbol changes, traversing graph blast radii, synthesizing LLM reviews, and updating job history).

In a second terminal, start the background worker:

```cmd
uv run python scripts/worker.py
```

Expected worker startup output:

```text
Starting ARQ PR Analysis Worker process (Environment: development) connecting to Redis at 'redis://127.0.0.1:6379'...
[WorkerLifecycle:startup_complete] Worker startup validation completed successfully.
```

> [!IMPORTANT]
> The background worker must be running for Pull Request analysis jobs submitted via the web console or `POST /analysis/pr` to execute. Without an active worker, jobs will remain in `QUEUED` status.
> 
> Unlike the FastAPI server which reloads automatically via `--reload`, background worker processes in Python load modules once into memory at startup. When modifying backend code in `app/`, restart the worker process to load the latest changes.

---

# Frontend & Visual Identity

The repository includes a modern, high-performance developer intelligence console styled in **Midnight Graphite & Electric Blue**.

After starting the API, open:

```text
http://localhost:8000/
```

### Visual Identity & Theme
- **Color Palette**:
  - Header: `#0C1422`
  - Left Primary Navigation: `#131E30`
  - Right Context Inspector: `#101A2A`
  - Main Workspace Canvas: `#0A1120`
  - Content Cards & Containers: `#162338`
  - Elevated Cards & Modals: `#1D2C43`
  - Accent / Brand Blue: `#4F8CFF` (Hover: `#3478F6`, Active: `#1D3B70`)
- **Branding**:
  - Custom geometric Code Graph Intelligence logo (`<svg>` with interconnected nodes and electric blue gradients).
  - Dedicated browser favicon (`frontend/favicon.svg`).
- **Graph Node Palette**:
  - File: `#60A5FA`
  - Class: `#C084FC`
  - Function / Method: `#34D399`
  - API Endpoint: `#FBBF24`
  - API Client Call: `#F472B6`
  - API Contract: `#22D3EE`

### Primary Navigation Views
The left navigation exposes exactly six primary features:
1. **Codebase Query (Graph RAG)**: Natural-language query interface with structured markdown answers (Direct Answer, Explanation, Relevant Files & Symbols, Why It Matters, Recommended Action).
2. **Impact Analysis**: Target symbol and file blast-radius analysis with depth controls and Cytoscape dependency subgraphs.
3. **API Flow Analysis**: Endpoint-to-client route mapping across languages.
4. **Pull Request Analysis**: Evidence-based review findings with risk assessment and asynchronous job history.
5. **Architecture Intelligence & Visualization**: Interactive module graph, architectural layer decomposition cards (Presentation, Logic, Persistence, Infrastructure), and system entry point pills.
6. **Code Quality & Security Analysis**: Severity breakdown cards (Critical, High, Medium, Low), category filter tabs, search filter, masked code snippets, and click-to-view source code modal.

### Interactive Graph Explorer (Cytoscape.js)
The console includes a responsive, high-performance canvas powered by **Cytoscape.js (v3.28.1)** for Codebase Query subgraphs, Impact Analysis blast radii, and Architecture module graphs:
* **Interactive Navigation**: Drag to pan, scroll to zoom, and click the "Fit" button to re-center the active graph.
* **Neighborhood Highlighting**: Clicking any node highlights its direct upstream callers and downstream dependencies while dimming unrelated graph elements.
* **Context Inspector**: The right inspector panel dynamically displays selected node metadata, qualified names, language, line ranges, and inbound/outbound edge connections.
* **Full-Screen Canvas**: Expand graph visualizations into an edge-to-edge modal for deep exploration of complex code topologies.
* **Safe Source Code Viewer**: Click-to-view modal fetching exact source code via `GET /source` with strict directory traversal protection.

---

# API Surface

The API is organized into several functional areas.

| Area      | Purpose                                       |
| --------- | --------------------------------------------- |
| Health    | Service and infrastructure health             |
| Ingestion | Repository ingestion and indexing             |
| Query     | Codebase Graph RAG queries                    |
| Graph     | Graph inspection and graph-related operations |
| Analysis  | Code and impact analysis                      |
| Source    | Source/repository operations                  |
| Jobs      | Background job status and management          |
| Webhooks  | SCM webhook processing                        |

Representative endpoints include:

```text
GET  /health

POST /repositories/ingest

GET  /repositories

POST /query

GET  /graph/{repository_id}
```

For the complete API surface, see:

`docs/API.md`

---

# Repository Ingestion Pipeline

The ingestion pipeline converts a repository into the representations required for intelligent analysis.

```text
Repository
    │
    ▼
Repository Loader
    │
    ▼
File Discovery
    │
    ▼
Language Detection
    │
    ▼
AST / Structural Parsing
    │
    ├───────────────────────┐
    ▼                       ▼
Knowledge Graph         Semantic Chunks
    │                       │
    ▼                       ▼
Neo4j                   Embedding Model
                            │
                            ▼
                          Qdrant
```

The ingestion process therefore creates both:

1. a **structural representation**
2. a **semantic representation**

of the same repository.

---

# Example Questions

Once a repository has been indexed, the platform is designed for questions such as:

### Repository comprehension

```text
How is authentication implemented?
```

```text
Where is user registration handled?
```

```text
Which modules are responsible for database access?
```

### Dependency reasoning

```text
Which functions call this method?
```

```text
What classes inherit from this class?
```

```text
What modules depend on this component?
```

### Impact analysis

```text
What could be affected if this function changes?
```

```text
Which APIs depend on this service?
```

### API analysis

```text
Which internal functions implement this API endpoint?
```

```text
What dependencies are involved in this request flow?
```

### Architecture analysis

```text
What are the primary architectural layers and cross-module dependencies?
```

```text
Where are the main entry points and high-level controllers located?
```

### Code quality and security analysis

```text
Are there any hardcoded secrets, tokens, or private keys in the repository?
```

```text
Which functions exceed cyclomatic complexity thresholds or contain maintainability smells?
```

### Pull-request analysis

```text
What parts of the codebase could be affected by this PR?
```

These examples illustrate the type of **multi-hop software reasoning** the platform is designed to support.

---

# Evaluation and Testing

The project includes automated test coverage with over 134 unit and integration tests across parsing, graph construction, vector retrieval, LangGraph reasoning, LLM abstractions, async jobs, and PR analysis.

## Unit tests

Run all unit tests:

```cmd
uv run pytest tests/unit
```

Run targeted PR Analysis regression test suite:

```cmd
uv run pytest tests/unit/test_pr_zero_change_regression.py -v
```

## Integration tests

Infrastructure-dependent integration tests require the supporting services (Neo4j, Qdrant, Redis) to be available:

```cmd
uv run pytest tests/integration -m integration
```

## Full test suite

Run the complete test suite:

```cmd
uv run pytest
```

The project has been validated with a comprehensive automated test suite during development, including unit and integration coverage across parsing, graph construction, retrieval, LLM providers, evaluation, jobs, PR workflows, and analysis components.

---

# Code Quality

Run Ruff:

```cmd
uv run ruff check .
```

Compile-check the application:

```cmd
uv run python -m compileall app
```

The repository also contains configuration for static/type analysis through:

```text
pyrightconfig.json
pyrefly.toml
```

---

# LLM Smoke Test

The repository includes a dedicated OpenAI smoke-test script:

```cmd
uv run python scripts\test_openai_smoke.py
```

This provides a lightweight way to verify that the configured OpenAI provider can be initialized and invoked successfully.

---

# Evaluation Workflow

The project contains an evaluation subsystem for measuring aspects of the platform's behavior.

Relevant components include:

```text
app/evaluation/
├── answer_evaluator.py
├── dataset_loader.py
├── evaluation_runner.py
├── graph_evaluator.py
├── latency_tracker.py
├── metrics.py
├── models.py
└── report_generator.py
```

Evaluation concerns include areas such as:

* retrieval behavior
* answer quality
* graph reasoning
* latency
* evaluation metrics

The project also includes an evaluation runner:

```cmd
uv run python scripts\run_evaluation.py
```

Detailed evaluation information is documented in:

`docs/EVALUATION.md`

---

# Production-Oriented Engineering

This project was intentionally designed beyond a minimal RAG proof of concept.

Important engineering concerns addressed in the architecture include:

### Modular architecture

Major responsibilities are separated into independent modules:

```text
API
Ingestion
Parsing
Graph
Embeddings
Retrieval
Reasoning
LLM
Diff
PR
Jobs
Integrations
Evaluation
```

### Provider abstraction

LLM invocation is isolated behind an interface rather than being scattered throughout application code.

### Async processing

Long-running repository and PR operations can be processed through background workers.

### Job reliability

The job subsystem includes mechanisms for:

* retries
* idempotency
* concurrency
* job history
* failure handling
* dead-letter handling

### Repository integrations

Source-control provider integrations are isolated behind integration abstractions.

### Testability

The project contains dedicated unit tests, integration tests, repository fixtures, and multi-language test fixtures.

---

# Security Considerations

Never commit secrets.

The following should remain local:

```text
.env
.env.*
API keys
access tokens
database passwords
GitHub/GitLab credentials
```

Use `.env.example` as the public configuration template.

Example:

```ini
OPENAI_API_KEY=""
GITHUB_TOKEN=""
GITLAB_TOKEN=""
```

Do not replace these placeholders with real credentials before committing.

### Environment Configuration Variables (`.env.example`)

| Variable | Default / Example | Purpose |
| :--- | :--- | :--- |
| `APP_NAME` | `"Codebase Graph Intelligence Platform"` | Application runtime name |
| `ENVIRONMENT` | `"development"` | Runtime mode (`development`, `test`, `production`) |
| `LOG_LEVEL` | `"INFO"` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_FORMAT` | `"text"` | Log serialization (`text` for console, `json` for production) |
| `NEO4J_URI` | `"bolt://localhost:7687"` | Neo4j Bolt driver endpoint |
| `NEO4J_USERNAME` | `"neo4j"` | Neo4j database username |
| `NEO4J_PASSWORD` | `"password"` | Neo4j database password |
| `NEO4J_DATABASE` | `"neo4j"` | Target Neo4j database name |
| `QDRANT_URL` | `"http://localhost:6333"` | Qdrant vector database HTTP endpoint |
| `QDRANT_COLLECTION` | `"codebase_chunks"` | Vector collection name for code chunk embeddings |
| `REDIS_URL` | `"redis://127.0.0.1:6379"` | Redis broker URL for ARQ job queue and idempotency |
| `JOB_TTL_SECONDS` | `86400` | Expiration TTL for completed job records (24 hours) |
| `WORKER_MAX_JOBS` | `10` | Maximum concurrent background jobs per worker process |
| `WORKER_JOB_TIMEOUT` | `300` | Worker execution timeout threshold in seconds |
| `EMBEDDING_MODEL` | `"BAAI/bge-small-en-v1.5"` | Local Hugging Face sentence-transformers model |
| `LLM_PROVIDER` | `"openai"` | Active LLM provider abstraction |
| `OPENAI_API_KEY` | `""` | OpenAI API authentication key |
| `OPENAI_MODEL` | `"gpt-6-luna"` / `"gpt-4o-mini"` | Production reasoning model |
| `GITHUB_TOKEN` | `""` | GitHub personal access token for remote PR fetching |
| `GITHUB_WEBHOOK_SECRET` | `""` | HMAC secret for authenticating GitHub webhooks |
| `GITLAB_TOKEN` | `""` | GitLab API token for merge-request discussions |
| `GITLAB_WEBHOOK_SECRET` | `""` | Secret token for authenticating GitLab webhooks |

---

# Troubleshooting

### Redis Connection Timeouts on Windows
On Windows systems, `localhost` may initially resolve to IPv6 (`::1`), causing connection timeouts if the local Redis instance is bound strictly to IPv4 (`127.0.0.1`).
Ensure `REDIS_URL` in `.env` is set to:
```ini
REDIS_URL="redis://127.0.0.1:6379"
```

### Worker Process Outdated After Source Code Changes
Unlike FastAPI with `--reload`, Python background workers load code into memory once at startup. If you modify source code in `app/`, restart the worker process:
```cmd
# Stop worker (Ctrl+C) and restart:
uv run python scripts/worker.py
```

### Neo4j APOC Procedures Required
Ensure `NEO4J_PLUGINS=["apoc"]` and `NEO4J_dbms_security_procedures_unrestricted=apoc.*` are present in `docker-compose.yml`. Neo4j APOC procedures are required for advanced subgraph and traversal queries.

---

# System Boundaries & Known Limitations

To maintain engineering transparency and establish realistic expectations for technical reviews:

1. **Static Analysis Scope**: The platform parses static Abstract Syntax Trees (ASTs) and traverses static relationship graphs. It does not perform dynamic runtime profiling, execution trace capture, or dynamic symbolic execution. Code paths gated by dynamic runtime values, reflection, or dynamic imports may not be fully resolved.
2. **Quality & Security Scanner Boundaries**: The Code Quality & Security scanner utilizes static AST pattern recognition and regular expression matching. It effectively catches common maintainability smells (excessive complexity, long functions, wildcard imports), standard injection vulnerabilities, dynamic execution (`eval`, `exec`), and known credential patterns (OpenAI, AWS, GitHub tokens). It is not an exhaustive static application security testing (SAST) tool and does not guarantee detection of obfuscated secrets, zero-day vulnerabilities, or advanced multi-stage taint flows.
3. **Graph Traversal Limits**: The knowledge graph traversal depth defaults to 3 hops (configurable from 1 to 5 hops). Deeply nested transitive dependency chains beyond the configured depth are bounded to ensure interactive query latency.
4. **Answer Groundedness Enforcement**: The platform enforces rigorous groundedness validation (`AnswerValidator`). If the LLM generates an explanation citing files or symbols absent from the retrieved graph subgraphs or vector chunks, the response is marked with a groundedness warning to alert developers against unverified hallucinations.
5. **No Autonomous Code Modification**: The platform is an engineering intelligence and review assistant—it produces evidence-based insights, risk scores, and PR review comments, but does not autonomously modify source code or bypass human engineering approval.

---

# Documentation

Additional technical documentation is available in the `docs/` directory.

| Document               | Purpose                      |
| ---------------------- | ---------------------------- |
| `docs/API.md`          | API documentation            |
| `docs/ARCHITECTURE.md` | Detailed system architecture |
| `docs/DEPLOYMENT.md`   | Deployment guidance          |
| `docs/DEVELOPMENT.md`  | Development workflow         |
| `docs/EVALUATION.md`   | Evaluation methodology       |
| `docs/OPERATIONS.md`   | Operational guidance         |

---

# Development Philosophy

The platform is built around a central idea:

> **Software should be represented as both meaning and structure.**

Semantic embeddings capture what code is about.

Knowledge graphs capture how code is connected.

Neither representation is sufficient for every software-engineering question.

The combination enables a richer model:

```text
                    CODEBASE
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
     SEMANTIC VIEW             STRUCTURAL VIEW
          │                         │
          ▼                         ▼
       Qdrant                    Neo4j
          │                         │
          └────────────┬────────────┘
                       ▼
                 Hybrid Retrieval
                       │
                       ▼
                    RRF/Fusion
                       │
                       ▼
                  LangGraph
                       │
                       ▼
                 LLM Reasoning
                       │
                       ▼
              Software Intelligence
```

This architecture is intended to make the system useful for **understanding, navigating, analyzing, and reasoning about software repositories** rather than simply retrieving code snippets.

---

# Roadmap / Extension Areas

The architecture provides a foundation for further capabilities such as:

* richer cross-language relationship extraction
* improved graph-based retrieval strategies
* more advanced repository-level reasoning
* deeper CI/CD integration
* automated code-review workflows
* additional source-control providers
* improved evaluation benchmarks
* repository-scale performance optimization
* richer developer-facing visualizations

---

# Project Status

**Current release:** `v2.0.0-architecture-quality`

The project includes:

* Graph RAG architecture (LangGraph + OpenAI)
* Neo4j software knowledge graph
* Qdrant semantic retrieval
* Hybrid retrieval / RRF
* Code impact analysis & blast radius exploration
* API flow analysis (endpoint-to-client matching)
* Evidence-based Pull Request analysis (powered by internal structural diff engine)
* Architecture Intelligence & Visualization (layers, modules, entry points)
* Code Quality & Security Analysis (AST smells, credential scanning with secret masking)
* Multi-language parsing (Python, Go, Java, JavaScript, TypeScript)
* GitHub & GitLab provider integrations
* Async job processing with Redis + ARQ workers
* Midnight Graphite & Electric Blue developer intelligence console
* Evaluation framework and automated test suite

---

# License

Add the project's chosen license here before publishing if a specific open-source license is intended.

---

# Author / Portfolio

**Codebase Graph Intelligence Platform**

Built as a production-oriented software engineering intelligence project demonstrating:

```text
Graph RAG
Knowledge Graphs
Vector Search
Hybrid Retrieval
RRF
LLM Engineering
LangGraph
AST / Code Parsing
Multi-Language Analysis
FastAPI
Neo4j
Qdrant
Redis
ARQ
Async Systems
PR Automation
Code Impact Analysis
Evaluation
Testing
Production Engineering
```

---

## Quick Start

For the shortest path from clone to running application:

```cmd
cd /d "D:\PROJECTS\CODEBASE GRAPH INTELLIGENCE PLATFORM"

# 1. Synchronize Python virtual environment
uv sync

# 2. Copy and configure environment variables
copy .env.example .env

# 3. Start local databases (Neo4j, Qdrant, Redis)
docker-compose up -d

# 4. Terminal 1: Start FastAPI application server
uv run uvicorn app.api.main:app --reload --port 8000

# 5. Terminal 2: Start ARQ background worker (for asynchronous PR Analysis)
uv run python scripts/worker.py
```

Then open:

```text
http://localhost:8000/
```

API documentation:

```text
http://localhost:8000/docs
```

Run tests:

```cmd
uv run pytest
```

Run the OpenAI provider smoke test:

```cmd
uv run python scripts\test_openai_smoke.py
```

---

> **The Codebase Graph Intelligence Platform combines structural code intelligence with semantic retrieval to provide a foundation for repository-scale software reasoning.**
