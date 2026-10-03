"""Integration tests for Neo4j database connection."""

import pytest

from app.graph.neo4j_client import Neo4jClient
from app.utils.exceptions import GraphDatabaseError


@pytest.mark.integration
def test_neo4j_connection_or_handled_error():
    client = Neo4jClient()
    try:
        connected = client.verify_connectivity()
        assert connected is True
    except GraphDatabaseError as e:
        # Service might not be running in Docker during unit run, verify exception is handled cleanly
        pytest.skip(f"Neo4j Docker service not running: {e}")
