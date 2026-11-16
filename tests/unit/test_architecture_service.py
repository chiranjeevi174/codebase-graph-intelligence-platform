"""Unit tests for Architecture Intelligence & Visualization Service."""

from pathlib import Path
from unittest.mock import MagicMock

from app.analysis.architecture_service import ArchitectureIntelligenceService
from app.models.entities import ArchitectureAnalysisRequest


def test_architecture_discovery_filesystem_sample_repo():
    """Verify static architecture discovery on sample_repo fixture."""
    service = ArchitectureIntelligenceService(neo4j_client=MagicMock())
    # Force Neo4j query to return empty so filesystem discovery runs
    service.client.execute_read.return_value = []

    req = ArchitectureAnalysisRequest(
        repository_id="sample_repo",
        repo_path=str(Path("tests/fixtures/sample_repo").resolve()),
        level="overview",
    )
    result = service.analyze_architecture(req)

    assert result.repository_id == "sample_repo"
    assert result.summary.total_files > 0
    assert len(result.layers) > 0
    assert len(result.nodes) > 0
    assert len(result.edges) > 0

    # Verify layer classifications exist
    layer_names = [layer.name for layer in result.layers]
    assert any("Service" in name or "Logic" in name for name in layer_names)

    # Verify entry points identified
    assert len(result.entry_points) > 0
    entry_names = [ep["name"] for ep in result.entry_points]
    assert "main.py" in entry_names

    # Verify grounded explanation
    assert result.explanation is not None
    assert len(result.explanation) > 50


def test_architecture_discovery_detailed_level():
    """Verify detailed level extracts classes and functions as child nodes."""
    service = ArchitectureIntelligenceService(neo4j_client=MagicMock())
    service.client.execute_read.return_value = []

    req = ArchitectureAnalysisRequest(
        repository_id="sample_repo",
        repo_path=str(Path("tests/fixtures/sample_repo").resolve()),
        level="detailed",
    )
    result = service.analyze_architecture(req)

    assert result.summary.total_files > 0
    # Detailed mode should contain Class or Function symbol nodes
    node_labels = {n.label for n in result.nodes}
    assert "File" in node_labels


def test_architecture_neo4j_mock_discovery():
    """Verify architecture construction when Neo4j returns graph nodes and relationships."""
    mock_client = MagicMock()

    mock_client.execute_read.side_effect = [
        # Node rows
        [
            {
                "file_path": "services/user_service.py",
                "relative_path": "services/user_service.py",
                "language": "python",
                "loc": 60,
                "symbol_type": "Class",
                "symbol_name": "UserService",
                "symbol_qn": "services.UserService",
                "symbol_id": "sym_user_service",
            },
            {
                "file_path": "main.py",
                "relative_path": "main.py",
                "language": "python",
                "loc": 30,
                "symbol_type": "Function",
                "symbol_name": "main",
                "symbol_qn": "main.main",
                "symbol_id": "sym_main",
            },
        ],
        # Edge rows
        [
            {
                "source": "main.main",
                "target": "services.UserService",
                "rel_type": "CALLS",
                "source_file": "main.py",
                "target_file": "services/user_service.py",
            }
        ],
    ]

    service = ArchitectureIntelligenceService(neo4j_client=mock_client)
    req = ArchitectureAnalysisRequest(repository_id="mock_repo", level="overview")
    result = service.analyze_architecture(req)

    assert result.repository_id == "mock_repo"
    assert result.summary.total_files == 2
    assert len(result.nodes) == 2
    assert len(result.edges) == 1
    assert result.edges[0].type == "CALLS"
