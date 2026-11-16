"""Unit tests for AnswerValidator component."""

from app.models.entities import GraphNode, GraphPath, NormalizedSearchResult, ResolvedEntity
from app.reasoning.answer_validator import AnswerValidator


def test_answer_validator_grounded_answer():
    validator = AnswerValidator()

    resolved = [
        ResolvedEntity(
            symbol_id="1",
            name="create_user",
            qualified_name="services.UserService.create_user",
            symbol_type="Method",
            file_path="services/user_service.py",
            start_line=10,
            end_line=30,
        )
    ]

    fused = [
        NormalizedSearchResult(
            id="c1",
            source="both",
            repository_id="repo",
            file_path="services/user_service.py",
            start_line=10,
            end_line=30,
            content="def create_user(): pass",
        )
    ]

    good_answer = "UserService.create_user is defined in services/user_service.py:10-30 and creates a user entity."
    is_valid, errors = validator.validate(good_answer, fused_results=fused, resolved_entities=resolved)
    assert is_valid is True
    assert len(errors) == 0


def test_answer_validator_ungrounded_file():
    validator = AnswerValidator()

    resolved = []
    fused = [
        NormalizedSearchResult(
            id="c1",
            source="semantic",
            repository_id="repo",
            file_path="services/user_service.py",
            start_line=10,
            end_line=30,
            content="def create_user(): pass",
        )
    ]

    bad_answer = "The function is defined in non_existent_file.py:50."
    is_valid, errors = validator.validate(bad_answer, fused_results=fused, resolved_entities=resolved)
    assert is_valid is False
    assert len(errors) == 1
    assert "non_existent_file.py" in errors[0]


def test_answer_validator_ignores_tech_names():
    """Ensure runtime and framework names like Node.js and Express.js do not cause false positives."""
    validator = AnswerValidator()
    fused = [
        NormalizedSearchResult(
            id="c1",
            source="semantic",
            repository_id="repo",
            file_path="app/server.js",
            start_line=1,
            end_line=20,
            content="console.log('server running');",
        )
    ]

    answer = "The application backend runs on Node.js using Express.js for routing defined in app/server.js."
    is_valid, errors = validator.validate(answer, fused_results=fused, resolved_entities=[])
    assert is_valid is True
    assert len(errors) == 0


def test_answer_validator_handles_negations_gracefully():
    """Ensure stating that a file does not exist or was not found does not fail validation."""
    validator = AnswerValidator()
    fused = [
        NormalizedSearchResult(
            id="c1",
            source="semantic",
            repository_id="repo",
            file_path="app/main.py",
            start_line=1,
            end_line=10,
            content="print('main')",
        )
    ]

    answer = "The file auth_service.py was not found in the codebase. Only app/main.py is available."
    is_valid, errors = validator.validate(answer, fused_results=fused, resolved_entities=[])
    assert is_valid is True
    assert len(errors) == 0


def test_answer_validator_cross_platform_path_normalization():
    """Ensure Windows backslashes in context match forward slashes in generated answer."""
    validator = AnswerValidator()
    fused = [
        NormalizedSearchResult(
            id="c1",
            source="semantic",
            repository_id="repo",
            file_path="app\\workflows\\graph_rag.py",
            start_line=1,
            end_line=50,
            content="class GraphRAGPipeline: pass",
        )
    ]

    answer = "Graph RAG pipeline is implemented in app/workflows/graph_rag.py:1-50."
    is_valid, errors = validator.validate(answer, fused_results=fused, resolved_entities=[])
    assert is_valid is True
    assert len(errors) == 0


def test_answer_validator_content_embedded_files():
    """Ensure files mentioned inside chunk content or import statements are recognized."""
    validator = AnswerValidator()
    fused = [
        NormalizedSearchResult(
            id="c1",
            source="semantic",
            repository_id="repo",
            file_path="app/main.py",
            start_line=1,
            end_line=10,
            content="from app.diff.diff_analyzer import StructuralDiffAnalyzer # see diff_analyzer.py",
        )
    ]

    answer = "The main entrypoint delegates to diff_analyzer.py for structural diff analysis."
    is_valid, errors = validator.validate(answer, fused_results=fused, resolved_entities=[])
    assert is_valid is True
    assert len(errors) == 0


def test_answer_validator_subgraph_and_path_files():
    """Ensure files from graph paths and subgraph nodes are included in valid files."""
    validator = AnswerValidator()
    node_a = GraphNode(id="n1", name="OrderService", file_path="app/services/orders.py")
    node_b = GraphNode(id="n2", name="PaymentService", file_path="app/services/payments.py")
    path = GraphPath(source_node=node_a, target_node=node_b, relationships=["CALLS"])

    answer = "OrderService calls PaymentService located in app/services/payments.py."
    is_valid, errors = validator.validate(answer, fused_results=[], resolved_entities=[], graph_paths=[path])
    assert is_valid is True
    assert len(errors) == 0


def test_answer_validator_empty_or_whitespace_answer():
    """Ensure empty or whitespace-only answers fail with clear message."""
    validator = AnswerValidator()
    is_valid, errors = validator.validate("", fused_results=[], resolved_entities=[])
    assert is_valid is False
    assert errors == ["Empty answer generated."]

    is_valid, errors = validator.validate("   \n\t  ", fused_results=[], resolved_entities=[])
    assert is_valid is False
    assert errors == ["Empty answer generated."]
