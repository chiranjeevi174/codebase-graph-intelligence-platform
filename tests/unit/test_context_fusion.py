"""Unit tests for ContextFusion component."""

from app.models.entities import NormalizedSearchResult, ResolvedEntity
from app.retrieval.context_fusion import ContextFusion


def test_context_fusion_formatting():
    fusion = ContextFusion()

    resolved = [
        ResolvedEntity(
            symbol_id="sym1",
            name="UserService",
            qualified_name="services.UserService",
            symbol_type="Class",
            file_path="services/user.py",
            start_line=5,
            end_line=50,
            match_type="exact",
        )
    ]

    fused_results = [
        NormalizedSearchResult(
            id="chunk1",
            source="both",
            repository_id="sample",
            file_path="services/user.py",
            symbol_name="create_user",
            qualified_name="services.UserService.create_user",
            symbol_type="Method",
            start_line=10,
            end_line=25,
            content="def create_user(self):\n    pass",
            score=0.9,
            rrf_score=0.032,
        )
    ]

    context = fusion.fuse_context(
        query="What does UserService do?",
        fused_results=fused_results,
        resolved_entities=resolved,
    )

    assert "### RESOLVED CODE ENTITIES:" in context
    assert "services.UserService" in context
    assert "### RETRIEVED CODE SNIPPETS & METADATA:" in context
    assert "File: services/user.py:10-25" in context
    assert "def create_user(self):" in context
