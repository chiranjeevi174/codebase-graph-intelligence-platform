"""Unit tests for RepositoryIngestionService using sample fixture repo and mock clients."""

from pathlib import Path
from unittest.mock import MagicMock

from app.ingestion.repository_service import RepositoryIngestionService


def test_ingest_sample_repo_mocked():
    sample_path = str(Path("tests/fixtures/sample_repo").resolve())

    mock_graph_builder = MagicMock()
    mock_embedding_service = MagicMock()

    service = RepositoryIngestionService(
        graph_builder=mock_graph_builder,
        embedding_service=mock_embedding_service,
    )

    result = service.ingest_repository(target=sample_path)

    assert result.name == "sample_repo"
    assert result.files_discovered == 5
    assert result.files_processed == 5
    assert result.files_failed == 0
    assert result.symbols_extracted > 0
    assert result.relationships_extracted > 0
    assert result.chunks_created > 0
    assert mock_graph_builder.create_repository_node.called
    assert mock_graph_builder.ingest_extracted_data.call_count == 5
    assert mock_embedding_service.process_and_store_chunks.call_count == 5
