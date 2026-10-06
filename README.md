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

The result is a system designed for **repository comprehension, dependency analysis, code impact analysis, API analysis, structural diff analysis, pull-request intelligence, and multi-hop code reasoning**.

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

# 8. Structural Diff Analysis

The platform includes structural code-diff capabilities beyond simple line-by-line comparison.

The diff subsystem contains analysis for areas such as:

* API differences
* symbol differences
* signature differences
* structural differences
* relationship differences
* Git diff processing

This makes it possible to reason about how a code change affects the software structure rather than only reporting changed lines.

---

# 9. Pull Request Intelligence

The platform includes pull-request analysis workflows.

The PR subsystem supports:

* PR analysis
* webhook-driven processing
* PR comments
* asynchronous processing
* job tracking
* analysis services
* repository integration

A conceptual workflow is:

```text
Pull Request
      │
      ▼
Webhook
      │
      ▼
Async Job
      │
      ▼
Repository / Diff Analysis
      │
      ▼
Structural + Graph Analysis
      │
      ▼
LLM Reasoning
      │
      ▼
PR Analysis / Feedback
```

---

# 10. GitHub and GitLab Integration

The integration layer provides repository-provider abstractions for external source-control systems.

Supported integrations include:

* GitHub
* GitLab

The architecture separates provider-specific functionality from the core analysis system, making the platform easier to extend.

---

# 11. Asynchronous Job Processing

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

# 12. Multi-Language Code Analysis

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
│   │   └── impact_service.py
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
│   ├── index.html
│   ├── css/
│   └── js/
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

# Frontend

The repository includes a browser-based frontend for interacting with the platform.

After starting the API, open:

```text
http://localhost:8000/
```

The frontend provides interfaces for interacting with functionality exposed by the backend, including repository analysis, querying, graph-related information, impact analysis, diff analysis, and PR workflows.

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

### Change analysis

```text
What structural changes were introduced by this diff?
```

```text
Which symbols or relationships changed?
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

**Current release:** `v1.1.0-openai`

The project includes:

* Graph RAG architecture
* Neo4j software knowledge graph
* Qdrant semantic retrieval
* Hybrid retrieval / RRF
* LangGraph reasoning workflows
* OpenAI LLM provider
* Hugging Face embeddings
* Multi-language parsing
* Repository ingestion
* Code impact analysis
* API analysis
* Structural diff analysis
* Pull-request analysis
* GitHub/GitLab integrations
* Async job processing
* Redis + ARQ worker architecture
* Evaluation framework
* Unit and integration testing
* Browser frontend
* Production-oriented configuration and documentation

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
