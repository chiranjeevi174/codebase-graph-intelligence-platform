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

The reasoning layer is implemented using **LangGraph**.

A query can move through multiple reasoning/retrieval stages instead of performing a single retrieval operation.

Conceptually:

```text
User Question
      │
      ▼
Query Analysis
      │
      ▼
Entity / Concept Resolution
      │
      ▼
Graph Retrieval ─────┐
                     │
Semantic Retrieval ──┤
                     ▼
                 Context Fusion
                     │
                     ▼
              Graph Reasoning
                     │
                     ▼
                LLM Response
                     │
                     ▼
               Answer Validation
```

This architecture supports multi-hop questions that require understanding relationships between multiple parts of a repository.

---

# 6. Code Impact Analysis

The platform provides code impact analysis for understanding the potential consequences of changing a code element.

Example:

```text
Changed Function
      │
      ▼
Direct Callers
      │
      ▼
Indirect Callers
      │
      ▼
Dependent Components
      │
      ▼
Potentially Affected APIs / Files
```

This is particularly useful for questions such as:

> "What could break if this function changes?"

or:

> "Which components depend on this class?"

---

# 7. API Analysis

The platform includes API extraction and matching capabilities.

API-related analysis can connect:

```text
API Route
    │
    ▼
Controller / Handler
    │
    ▼
Service
    │
    ▼
Internal Functions
    │
    ▼
Dependencies
```

This helps connect externally visible APIs with the internal implementation structure.

---

# 8. Pull Request Analysis — Evidence-Based Review

The platform includes automated, evidence-based pull-request analysis workflows. Rather than presenting a generic diff, the PR review system investigates changed files, modified symbols, signature drifts, API changes, and potential downstream impacts.

The PR subsystem is powered by an internal structural diff engine (`app/diff/`):
* Symbol differences (added, removed, modified)
* Signature drifts (parameters, return types)
* API route differences
* Structural and relationship diffs

A conceptual workflow is:

```text
Pull Request
      │
      ▼
Webhook / API Trigger
      │
      ▼
Async Job Queue (Redis + ARQ)
      │
      ▼
Internal Structural Diff Engine (app/diff/)
      │
      ▼
Graph & Blast Radius Impact Analysis
      │
      ▼
Evidence-Based LLM Review Formulation
      │
      ▼
PR Sticky Comments & Job History
```

---

# 9. Architecture Intelligence & Visualization

The platform extracts and visualizes high-level codebase architecture directly from the Neo4j Knowledge Graph (with filesystem AST fallback).

Key capabilities:
* **Architecture Discovery**: Extracts modules, packages, files, classes, and cross-module connections.
* **Architectural Layer Classification**: Automatically categorizes code into Presentation / API, Business Logic & Services, Persistence & Storage, and Infrastructure & Utilities.
* **Entry Point Detection**: Highlights system entry points (e.g., `main.py`, server entry points, CLI handlers).
* **Interactive Visualization**: Canvas powered by Cytoscape with node selection, pan, zoom, neighborhood highlighting, and right-panel inspection.
* **Grounded Architecture Explanation**: Technical overview explaining module responsibilities and system topology without fabricating absent layers.

---

# 10. Code Quality & Security Analysis

The platform features static code quality and security scanning:
* **AST Code Quality Smells**: Identifies functions with high cyclomatic complexity (> 10), excessive length (> 50 lines), excessive parameters (> 6), mutable default arguments, wildcard imports, and silent bare exception suppression.
* **Security Vulnerability Patterns**: Detects dynamic code execution (`eval`, `exec`), command injection (`shell=True`, `os.system`), SQL injection patterns, and unverified SSL connections.
* **Credential & Secret Scanner**: Scans for OpenAI API keys, AWS access keys, GitHub personal access tokens, private keys, and hardcoded passwords.
* **Automated Secret Redaction**: All detected tokens are cryptographically masked (e.g., `sk-proj-****[REDACTED]****a1b2`). Raw credentials are never exposed in reports or logs.
* **Structured Findings**: Each finding includes severity, category, file location, masked code evidence, explanation, "Why It Matters", and recommended developer action.

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

| Layer              | Technology                         | Role                                  |
| ------------------ | ---------------------------------- | ------------------------------------- |
| Language           | Python 3.11                        | Core implementation                   |
| Package Management | `uv`                               | Environment and dependency management |
| API                | FastAPI                            | REST API                              |
| Server             | Uvicorn                            | ASGI application server               |
| Workflow           | LangGraph                          | Stateful reasoning workflows          |
| LLM Framework      | LangChain                          | LLM/retrieval integration             |
| LLM                | OpenAI                             | Production reasoning/generation       |
| Embeddings         | Hugging Face                       | Local semantic embeddings             |
| Embedding Model    | `BAAI/bge-small-en-v1.5`           | 384-dimensional embeddings            |
| Vector DB          | Qdrant                             | Semantic code retrieval               |
| Graph DB           | Neo4j 5                            | Software knowledge graph              |
| Job Queue          | ARQ                                | Async job processing                  |
| Queue/Cache        | Redis                              | Background job infrastructure         |
| Parsing            | AST / Tree-sitter based components | Source-code analysis                  |
| SCM                | Git / GitHub / GitLab              | Repository and PR integration         |
| Testing            | Pytest                             | Automated testing                     |
| Linting            | Ruff                               | Static quality checks                 |
| Type Analysis      | Pyright / Pyrefly configuration    | Type checking                         |
| Containers         | Docker Compose                     | Local infrastructure                  |

---

# Project Structure

```text
codebase-graph-intelligence-platform/
│
├── app/
│   ├── analysis/
│   │   ├── architecture_service.py
│   │   ├── impact_service.py
│   │   └── quality_security_service.py
│   │
│   ├── api/
│   │   ├── main.py
│   │   ├── middleware.py
│   │   └── routes/
│   │       ├── analysis.py
│   │       ├── graph.py
│   │       ├── health.py
│   │       ├── ingestion.py
│   │       ├── jobs.py
│   │       ├── query.py
│   │       ├── source.py
│   │       └── webhooks.py
│   │
│   ├── config/
│   │   └── settings.py
│   │
│   ├── diff/
│   │   ├── api_diff.py
│   │   ├── diff_analyzer.py
│   │   ├── relationship_diff.py
│   │   ├── signature_diff.py
│   │   ├── structural_diff.py
│   │   └── symbol_diff.py
│   │
│   ├── embeddings/
│   │   ├── embedder.py
│   │   ├── model.py
│   │   └── qdrant_store.py
│   │
│   ├── evaluation/
│   │   ├── answer_evaluator.py
│   │   ├── evaluation_runner.py
│   │   ├── graph_evaluator.py
│   │   ├── latency_tracker.py
│   │   └── metrics.py
│   │
│   ├── graph/
│   │   ├── graph_builder.py
│   │   ├── graph_queries.py
│   │   ├── neo4j_client.py
│   │   ├── schema.py
│   │   └── subgraph_builder.py
│   │
│   ├── ingestion/
│   │   ├── git_loader.py
│   │   ├── github_loader.py
│   │   └── repository_service.py
│   │
│   ├── integrations/
│   │   ├── github.py
│   │   └── gitlab.py
│   │
│   ├── jobs/
│   │   ├── models.py
│   │   ├── queue.py
│   │   ├── repository.py
│   │   ├── service.py
│   │   └── worker.py
│   │
│   ├── llm/
│   │   ├── adapters.py
│   │   ├── base.py
│   │   ├── factory.py
│   │   └── openai_provider.py
│   │
│   ├── models/
│   │   └── entities.py
│   │
│   ├── parsing/
│   │   ├── api_extractor.py
│   │   ├── api_matcher.py
│   │   ├── go_parser.py
│   │   ├── java_parser.py
│   │   ├── javascript_parser.py
│   │   ├── python_parser.py
│   │   ├── typescript_parser.py
│   │   └── ...
│   │
│   ├── pr/
│   │   ├── comment_formatter.py
│   │   ├── service.py
│   │   └── webhook_service.py
│   │
│   ├── reasoning/
│   │   ├── answer_validator.py
│   │   ├── entity_resolver.py
│   │   └── query_analyzer.py
│   │
│   ├── retrieval/
│   │   ├── context_fusion.py
│   │   ├── hybrid_retriever.py
│   │   ├── rrf.py
│   │   └── semantic_retriever.py
│   │
│   ├── workflows/
│   │   └── graph_rag.py
│   │
│   └── utils/
│
├── frontend/
│   ├── favicon.svg
│   ├── index.html
│   ├── css/
│   │   └── styles.css
│   └── js/
│       ├── api.js
│       ├── architecture.js
│       ├── graph.js
│       ├── impact.js
│       ├── pr.js
│       ├── quality_security.js
│       ├── query.js
│       ├── state.js
│       └── ui.js
│
├── scripts/
│   ├── analyze_api_flow.py
│   ├── analyze_diff.py
│   ├── analyze_impact.py
│   ├── analyze_pr.py
│   ├── ingest_repository.py
│   ├── run_evaluation.py
│   ├── test_openai_smoke.py
│   └── worker.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── docs/
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   ├── DEVELOPMENT.md
│   ├── EVALUATION.md
│   └── OPERATIONS.md
│
├── .env.example
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── uv.lock
├── README.md
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

The project includes both unit and integration testing.

## Unit tests

Run:

```cmd
uv run pytest tests/unit
```

## Integration tests

Infrastructure-dependent integration tests require the supporting services to be available:

```cmd
uv run pytest tests/integration -m integration
```

## Full test suite

Run:

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

uv sync

copy .env.example .env

docker-compose up -d

uv run uvicorn app.api.main:app --reload --port 8000
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
