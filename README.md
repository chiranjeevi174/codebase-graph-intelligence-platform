# Codebase Graph Intelligence Platform

Production-grade **Graph RAG** platform for software repository comprehension, structural dependency analysis, and multi-hop graph reasoning.

Unlike generic "chat-with-code" tools that perform simple textual search over text chunks, this platform constructs an explicit **Software Knowledge Graph** in Neo4j and pairs it with semantic code embeddings in Qdrant. The system reasons over AST-extracted structural relationships (call graphs, class inheritance, module imports, API routes) and code semantics using **LangGraph** workflows.

---

## 🏗 System Architecture

```
                    +------------------------------------------+
                    |        Developer / API Client            |
                    +--------------------+---------------------+
                                         |
                                         v
                    +--------------------+---------------------+
                    |           FastAPI Layer                  |
                    | (POST /ingest, POST /query, GET /health) |
                    +--------------------+---------------------+
                                         |
                                         v
                    +--------------------+---------------------+
                    |     Repository Ingestion & AST Parser    |
                    |   (Pathspec .gitignore, Python AST)     |
                    +---------+----------------------+---------+
                              |                      |
                              v                      v
             +----------------+-------+      +-------+----------------+
             | Software Knowledge Graph|      |    Semantic Embedder   |
             |   Extracted Entities   |      |  HF bge-small-en-v1.5  |
             +----------------+-------+      +-------+----------------+
                              |                      |
                              v                      v
                   +----------+----+          +------+----------+
                   |  Neo4j Graph  |          |  Qdrant Vector  |
                   |   Database    |          |    Database     |
                   +----------+----+          +------+----------+
                              \                      /
                               \                    /
                                v                  v
                    +------------------------------------------+
                    |       LangGraph Reasoning Engine         |
                    |  (Graph Retrieval + Semantic Fusion)     |
                    +--------------------+---------------------+
                                         |
                                         v
                    +--------------------+---------------------+
                    |     Provider-Agnostic LLM Layer          |
                    |     [OpenAI Production Provider]         |
                    +------------------------------------------+
```

---

## 🛠 Technology Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Language** | Python 3.11 | Primary language |
| **Environment / PM** | `uv` | High-performance Python package & environment manager |
| **Graph Database** | Neo4j 5 | Software entity graph & multi-hop relationship storage |
| **Vector Database** | Qdrant | Vector store for symbol-aware code chunk embeddings |
| **Embeddings** | Hugging Face (`BAAI/bge-small-en-v1.5`) | Local, LLM-independent 384-dim code vectorizer |
| **Orchestration** | LangGraph | State graph engine for multi-node Graph RAG workflow |
| **LLM Provider** | OpenAI (Production) | Provider-agnostic LLM abstraction layer |
| **Backend API** | FastAPI + Uvicorn | RESTful API server |

---

## 📊 Knowledge Graph Schema (Neo4j)

### Node Types
- `Repository`: Root repository container node
- `File`: Source file (`file_path`, `lines_of_code`, `language`)
- `Module`: Python module namespace
- `Class`: Class definition (`qualified_name`, `base_classes`, `docstring`)
- `Function`: Top-level function (`qualified_name`, `parameters`, `return_type`, `is_async`)
- `Method`: Class method (`qualified_name`, `class_name`, `is_classmethod`, `is_staticmethod`)

### Relationship Types
- `(:Repository)-[:CONTAINS]->(:File)`
- `(:File)-[:DEFINES]->(:Class|Function|Module)`
- `(:File)-[:IMPORTS {imported_symbol, alias, line_number}]->(:Module)`
- `(:Class|Function|Method)-[:CALLS {line_number, file_path}]->(:Function|Method)`
- `(:Class)-[:INHERITS]->(:Class)`

---

## ⚙️ Configuration & Environment Variables

Copy `.env.example` to `.env` and fill in API keys:

```bash
cp .env.example .env
```

Key configuration properties in `.env`:

```ini
APP_NAME="Codebase Graph Intelligence Platform"
ENVIRONMENT="development"
LOG_LEVEL="INFO"

# Database Connections
NEO4J_URI="bolt://localhost:7687"
NEO4J_USERNAME="neo4j"
NEO4J_PASSWORD="password"
QDRANT_URL="http://localhost:6333"

# Embeddings
EMBEDDING_MODEL="BAAI/bge-small-en-v1.5"

# LLM Provider Selection (openai)
LLM_PROVIDER="openai"

# API Keys
OPENAI_API_KEY="your-openai-api-key"
OPENAI_MODEL="gpt-4o-mini"
```

---

## 🚀 Running Local Databases (Docker Compose)

Start local Neo4j and Qdrant database services:

```bash
docker-compose up -d
```

Service ports:
- **Qdrant HTTP API**: [http://localhost:6333](http://localhost:6333)
- **Neo4j Browser UI**: [http://localhost:7474](http://localhost:7474) (Username: `neo4j`, Password: `password`)
- **Neo4j Bolt Protocol**: `bolt://localhost:7687`

---

## 🧪 Running Tests

Run all unit tests:

```bash
uv run pytest tests/unit
```

Run integration tests (requires local Docker services running):

```bash
uv run pytest tests/integration -m integration
```

Run linting with Ruff:

```bash
uv run ruff check .
```

---

## ⚡ Running the Server

Start the FastAPI application development server:

```bash
uv run codebase-graph-intelligence-platform
```
or
```bash
uv run uvicorn app.api.main:app --reload --port 8000
```

Access Interactive API Documentation:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🔌 API Endpoints Summary

- `GET /health`: System health status and database connections
- `POST /repositories/ingest`: Trigger repository loader, parsing, Neo4j graph building, and Qdrant embedding
- `GET /repositories`: List ingested repositories
- `POST /query`: Execute multi-hop Graph RAG reasoning over codebase
- `GET /graph/{repository_id}`: Retrieve graph structure metadata

---

## 🎯 LLM Provider Abstraction

The project uses a clean provider-agnostic LLM abstraction (`BaseLLMProvider`) powered canonical OpenAI implementation. Configure `LLM_PROVIDER` in your `.env` or environment:

```bash
# Production OpenAI Provider
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

The underlying Graph RAG reasoning pipeline automatically calls `get_llm()`, maintaining full independence between graph reasoning, embedding generation, and LLM text generation.
