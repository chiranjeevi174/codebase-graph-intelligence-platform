"""Unit tests for Codebase Query (Graph RAG) workflow, validation, and API response delivery."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.main import app
from app.graph.subgraph_builder import FocusedSubgraph
from app.models.entities import (
    GraphNode,
    GraphPath,
    GraphRAGResponse,
    NormalizedSearchResult,
    QueryAnalysisResult,
)
from app.workflows.graph_rag import (
    GraphRAGPipeline,
    GraphRAGState,
    answer_generation_node,
    subgraph_construction_node,
    validation_node,
)

client = TestClient(app)


def test_validation_node_preserves_answer_and_errors():
    """Ensure validation_node preserves answer and records validation error on ungrounded claims."""
    state: GraphRAGState = {
        "question": "Where is the payment gateway implemented?",
        "repository_id": "test_repo",
        "graph_top_k": 10,
        "semantic_top_k": 10,
        "final_top_k": 10,
        "max_hops": 2,
        "query_analysis": None,
        "resolved_entities": [],
        "graph_results": [],
        "semantic_results": [],
        "fused_results": [
            NormalizedSearchResult(
                id="c1",
                source="semantic",
                repository_id="test_repo",
                file_path="app/services/order_service.py",
                start_line=1,
                end_line=20,
                content="class OrderService: pass",
            )
        ],
        "subgraph": None,
        "graph_paths": [],
        "fused_context": "OrderService in app/services/order_service.py",
        "final_answer": "Payment gateway is implemented in app/services/unverified_gateway.py:45.",
        "validation_status": True,
        "validation_errors": [],
        "sources": ["app/services/order_service.py"],
    }

    result = validation_node(state)
    assert result["validation_status"] is False
    assert len(result["validation_errors"]) == 1
    assert "unverified_gateway.py" in result["validation_errors"][0]


def test_validation_node_passes_grounded_answer():
    """Ensure validation_node passes when citations exist in retrieved context."""
    state: GraphRAGState = {
        "question": "Where is the order service implemented?",
        "repository_id": "test_repo",
        "graph_top_k": 10,
        "semantic_top_k": 10,
        "final_top_k": 10,
        "max_hops": 2,
        "query_analysis": None,
        "resolved_entities": [],
        "graph_results": [],
        "semantic_results": [],
        "fused_results": [
            NormalizedSearchResult(
                id="c1",
                source="semantic",
                repository_id="test_repo",
                file_path="app/services/order_service.py",
                start_line=1,
                end_line=20,
                content="class OrderService: pass",
            )
        ],
        "subgraph": None,
        "graph_paths": [],
        "fused_context": "OrderService in app/services/order_service.py",
        "final_answer": "### Direct Answer\nOrderService is in app/services/order_service.py:1-20.",
        "validation_status": True,
        "validation_errors": [],
        "sources": ["app/services/order_service.py"],
    }

    result = validation_node(state)
    assert result["validation_status"] is True
    assert len(result["validation_errors"]) == 0


def test_subgraph_construction_falls_back_to_fused_candidates():
    """Ensure subgraph_construction_node evaluates fused/semantic results if resolved_entities is empty."""
    fused_chunk = NormalizedSearchResult(
        id="c1",
        source="semantic",
        repository_id="sample_repo",
        file_path="services/user_service.py",
        symbol_name="UserService",
        qualified_name="services.user_service.UserService",
        start_line=10,
        end_line=40,
        content="class UserService: pass",
    )

    state: GraphRAGState = {
        "question": "How does user management work?",
        "repository_id": "sample_repo",
        "graph_top_k": 10,
        "semantic_top_k": 10,
        "final_top_k": 10,
        "max_hops": 2,
        "query_analysis": None,
        "resolved_entities": [],  # Empty resolved entities
        "graph_results": [],
        "semantic_results": [],
        "fused_results": [fused_chunk],
        "subgraph": None,
        "graph_paths": [],
        "fused_context": None,
        "final_answer": None,
        "validation_status": True,
        "validation_errors": [],
        "sources": [],
    }

    mock_builder = MagicMock()
    mock_node_a = GraphNode(id="n1", name="UserService", file_path="services/user_service.py")
    mock_node_b = GraphNode(id="n2", name="UserHandler", file_path="handlers/user_handler.py")
    mock_path = GraphPath(source_node=mock_node_a, target_node=mock_node_b, relationships=["CALLS"])
    mock_subgraph = FocusedSubgraph(
        center_symbol="UserService",
        max_hops=2,
        nodes=[],
        edges=[],
        paths=[mock_path],
    )
    mock_builder.build_subgraph.return_value = mock_subgraph

    with patch("app.workflows.graph_rag.SubgraphBuilder", return_value=mock_builder):
        result = subgraph_construction_node(state)

    assert result["subgraph"] is not None
    assert len(result["graph_paths"]) == 1
    # Ensure builder was called with candidate from fused results
    mock_builder.build_subgraph.assert_called()
    called_seed = mock_builder.build_subgraph.call_args[1]["symbol_identifier"]
    assert called_seed in ["services.user_service.UserService", "UserService", "services/user_service.py"]


def test_pipeline_preserves_answer_when_validation_fails():
    """Ensure GraphRAGPipeline.run does not discard final_answer when validation_status is False."""
    mock_state = {
        "query_analysis": QueryAnalysisResult(query="test", intent="general_code_question"),
        "resolved_entities": [],
        "graph_results": [],
        "semantic_results": [],
        "fused_results": [],
        "graph_paths": [],
        "sources": ["app/main.py"],
        "final_answer": "This is a useful answer despite referencing unverified_extra.py:10.",
        "validation_status": False,
        "validation_errors": ["Answer cited ungrounded file path: 'unverified_extra.py'"],
    }

    with patch.object(GraphRAGPipeline, "__init__", lambda self: None):
        pipeline = GraphRAGPipeline()
        pipeline.app = MagicMock()
        pipeline.app.invoke.return_value = mock_state

        response: GraphRAGResponse = pipeline.run("test question")

        # Answer must NOT be discarded
        assert response.answer == "This is a useful answer despite referencing unverified_extra.py:10."
        assert response.validation_status is False
        assert len(response.validation_errors) == 1
        assert "unverified_extra.py" in response.validation_errors[0]
        assert response.confidence == 0.5


def test_query_api_returns_validation_status_and_errors():
    """Verify POST /query returns validation_status and validation_errors in response body."""
    mock_response = GraphRAGResponse(
        answer="Direct answer citing app/main.py:1-10.",
        repository_id="sample_repo",
        query="Explain main",
        intent="general_code_question",
        sources=["app/main.py"],
        graph_paths=[],
        retrieved_chunks=[],
        retrieval_summary="Fused 1 items",
        confidence=0.9,
        validation_status=True,
        validation_errors=[],
    )

    with patch.object(GraphRAGPipeline, "run", return_value=mock_response):
        payload = {
            "question": "Explain main",
            "repository_id": "sample_repo",
        }
        res = client.post("/query", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["answer"] == "Direct answer citing app/main.py:1-10."
        assert data["validation_status"] is True
        assert data["validation_errors"] == []


def test_query_api_handles_validation_warning_response():
    """Verify POST /query returns validation warnings without failing the HTTP request."""
    mock_response = GraphRAGResponse(
        answer="Answer with warning about ghost_module.py:5.",
        repository_id="sample_repo",
        query="Explain feature",
        intent="general_code_question",
        sources=["app/main.py"],
        graph_paths=[],
        retrieved_chunks=[],
        retrieval_summary="Fused 1 items",
        confidence=0.5,
        validation_status=False,
        validation_errors=["Answer cited ungrounded file path: 'ghost_module.py'"],
    )

    with patch.object(GraphRAGPipeline, "run", return_value=mock_response):
        payload = {
            "question": "Explain feature",
            "repository_id": "sample_repo",
        }
        res = client.post("/query", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["answer"] == "Answer with warning about ghost_module.py:5."
        assert data["validation_status"] is False
        assert len(data["validation_errors"]) == 1
        assert "ghost_module.py" in data["validation_errors"][0]


def test_answer_generation_node_handles_llm_failure():
    """Verify answer_generation_node safely catches LLM errors and returns None."""
    state: GraphRAGState = {
        "question": "How does auth work?",
        "repository_id": "sample_repo",
        "graph_top_k": 5,
        "semantic_top_k": 5,
        "final_top_k": 5,
        "max_hops": 2,
        "query_analysis": None,
        "resolved_entities": [],
        "graph_results": [],
        "semantic_results": [],
        "fused_results": [],
        "subgraph": None,
        "graph_paths": [],
        "fused_context": "Context snippet",
        "final_answer": None,
        "validation_status": True,
        "validation_errors": [],
        "sources": [],
    }

    mock_llm = MagicMock()
    mock_llm.generate.side_effect = Exception("OpenAI API rate limit or empty content")

    with patch("app.workflows.graph_rag.get_llm", return_value=mock_llm):
        result = answer_generation_node(state)

    assert result == {"final_answer": None}


def test_validation_node_skips_on_empty_answer():
    """Verify validation_node correctly skips validation and sets explicit error when answer is empty."""
    state: GraphRAGState = {
        "question": "How does auth work?",
        "repository_id": "sample_repo",
        "graph_top_k": 5,
        "semantic_top_k": 5,
        "final_top_k": 5,
        "max_hops": 2,
        "query_analysis": None,
        "resolved_entities": [],
        "graph_results": [],
        "semantic_results": [],
        "fused_results": [],
        "subgraph": None,
        "graph_paths": [],
        "fused_context": None,
        "final_answer": "",  # Empty answer
        "validation_status": True,
        "validation_errors": [],
        "sources": [],
    }

    result = validation_node(state)
    assert result["validation_status"] is False
    assert result["validation_errors"] == ["No answer generated by LLM provider."]


def test_graph_rag_pipeline_handles_empty_answer_gracefully():
    """Verify GraphRAGPipeline returns structured fallback response when LLM produced no answer."""
    mock_state = {
        "query_analysis": QueryAnalysisResult(query="test", intent="general_code_question"),
        "resolved_entities": [],
        "graph_results": [],
        "semantic_results": [],
        "fused_results": [],
        "graph_paths": [],
        "sources": [],
        "final_answer": None,
        "validation_status": False,
        "validation_errors": ["No answer generated by LLM provider."],
    }

    with patch.object(GraphRAGPipeline, "__init__", lambda self: None):
        pipeline = GraphRAGPipeline()
        pipeline.app = MagicMock()
        pipeline.app.invoke.return_value = mock_state

        response: GraphRAGResponse = pipeline.run("What is auth?")

        assert response.answer == "No answer could be generated from the available codebase context."
        assert response.validation_status is False
        assert response.validation_errors == ["No answer generated by LLM provider."]
        assert response.confidence == 0.0
