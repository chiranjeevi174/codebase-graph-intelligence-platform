"""Unit tests for GraphBuilder logic using mock Neo4j client."""

from unittest.mock import MagicMock

from app.graph.graph_builder import GraphBuilder
from app.models.entities import CodeSymbol, ExtractedCodeData, RepositoryInfo, SourceFile, SymbolType


def test_graph_builder_create_repository_node():
    mock_client = MagicMock()
    builder = GraphBuilder(client=mock_client)

    repo = RepositoryInfo(
        repository_id="test_repo",
        name="Test Repo",
        path="/path/to/test_repo",
        total_files=5,
        languages=["python"],
    )

    builder.create_repository_node(repo)
    mock_client.execute_write.assert_called_once()
    args, _ = mock_client.execute_write.call_args
    assert "MERGE (r:Repository" in args[0]
    assert args[1]["repository_id"] == "test_repo"


def test_graph_builder_ingest_extracted_data():
    mock_client = MagicMock()
    builder = GraphBuilder(client=mock_client)

    source_file = SourceFile(
        file_path="/path/main.py",
        relative_path="main.py",
        language="python",
        size_bytes=100,
        lines_of_code=10,
        extension=".py",
    )

    symbol = CodeSymbol(
        symbol_id="sym123",
        symbol_name="main",
        symbol_type=SymbolType.FUNCTION,
        file_path="main.py",
        start_line=1,
        end_line=5,
        qualified_name="main.main",
    )

    extracted = ExtractedCodeData(
        repository_id="test_repo",
        file_info=source_file,
        symbols=[symbol],
    )

    builder.ingest_extracted_data(extracted)
    assert mock_client.execute_write.call_count >= 2
