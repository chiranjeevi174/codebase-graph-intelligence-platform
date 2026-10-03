"""Unit tests for CodeImpactAnalysisService."""

from app.analysis.impact_service import CodeImpactAnalysisService
from app.models.entities import ImpactAnalysisRequest, ImpactNode, ImpactSummary, ResolvedEntity


def test_impact_analysis_models():
    node = ImpactNode(
        symbol_id="sym1",
        name="create_user",
        qualified_name="services.UserService.create_user",
        symbol_type="Method",
        file_path="services/user.py",
        start_line=10,
        end_line=25,
        relationship_type="CALLS",
        hop_count=1,
        impact_category="direct_dependent",
    )
    assert node.symbol_id == "sym1"
    assert node.hop_count == 1
    assert node.impact_category == "direct_dependent"

    summary = ImpactSummary(
        direct_dependents_count=2,
        transitive_dependents_count=1,
        direct_dependencies_count=1,
        transitive_dependencies_count=0,
        affected_files_count=3,
        affected_symbols_count=4,
        max_hops_used=2,
        analysis_truncated=False,
    )
    assert summary.affected_files_count == 3
    assert summary.analysis_truncated is False


def test_impact_analysis_service_mock_resolution(monkeypatch):
    service = CodeImpactAnalysisService()

    # Stub entity resolution
    def mock_resolve(*args, **kwargs):
        return [
            ResolvedEntity(
                symbol_id="user_service_id",
                name="UserService",
                qualified_name="services.UserService",
                symbol_type="Class",
                file_path="services/user_service.py",
                start_line=5,
                end_line=50,
            )
        ]

    # Stub graph queries
    def mock_find_dependents(*args, **kwargs):
        return [
            {
                "symbol_id": "main_id",
                "name": "main",
                "qualified_name": "main.main",
                "file_path": "main.py",
                "start_line": 1,
                "end_line": 20,
                "hop_count": 1,
                "rel_types": ["CALLS"],
                "labels": ["Function"],
            }
        ]

    def mock_find_dependencies(*args, **kwargs):
        return [
            {
                "symbol_id": "repo_id",
                "name": "UserRepository",
                "qualified_name": "repositories.UserRepository",
                "file_path": "repositories/user_repository.py",
                "start_line": 5,
                "end_line": 40,
                "hop_count": 1,
                "rel_types": ["DEPENDS_ON"],
                "labels": ["Class"],
            }
        ]

    monkeypatch.setattr(service.entity_resolver, "resolve", mock_resolve)
    monkeypatch.setattr(service.graph_query_manager, "find_transitive_dependents", mock_find_dependents)
    monkeypatch.setattr(service.graph_query_manager, "find_transitive_dependencies", mock_find_dependencies)

    req = ImpactAnalysisRequest(symbol="UserService", max_hops=2)
    res = service.analyze_impact(req)

    assert res.target.qualified_name == "services.UserService"
    assert res.summary.direct_dependents_count == 1
    assert res.summary.direct_dependencies_count == 1
    assert "main.py" in res.affected_files
    assert "services/user_service.py" in res.affected_files
    assert res.analysis_truncated is False
