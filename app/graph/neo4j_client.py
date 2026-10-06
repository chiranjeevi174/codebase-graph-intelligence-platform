"""Neo4j Database Client wrapper with connection pooling and query execution utilities."""

from typing import Any, LiteralString, cast

from neo4j import Driver, GraphDatabase
from neo4j.exceptions import Neo4jError

from app.config.settings import Settings, get_settings
from app.graph.schema import CYPHER_CONSTRAINTS, CYPHER_INDEXES
from app.utils.exceptions import GraphDatabaseError
from app.utils.logger import logger


class Neo4jClient:
    """Client wrapper for Neo4j Graph Database operations."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._driver: Driver | None = None

    def connect(self):
        """Establish connection to Neo4j instance if not already connected."""
        if self._driver is None:
            try:
                self._driver = GraphDatabase.driver(
                    self.settings.NEO4J_URI,
                    auth=(self.settings.NEO4J_USERNAME, self.settings.NEO4J_PASSWORD),
                )
                self.verify_connectivity()
                logger.info(f"Connected to Neo4j at {self.settings.NEO4J_URI}")
            except (Neo4jError, Exception) as e:  # noqa: BLE001
                self._driver = None
                raise GraphDatabaseError(f"Failed to connect to Neo4j database: {e}")

    def close(self):
        """Close Neo4j driver connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Closed Neo4j database connection.")

    def _get_driver(self) -> Driver:
        """Return non-optional connected Neo4j driver."""
        if not self._driver:
            self.connect()
        if self._driver is None:
            raise GraphDatabaseError("Neo4j database driver is not connected.")
        return self._driver

    def verify_connectivity(self) -> bool:
        """Verify database connectivity."""
        driver = self._get_driver()
        try:
            driver.verify_connectivity()
            return True
        except (Neo4jError, Exception) as e:  # noqa: BLE001
            raise GraphDatabaseError(f"Neo4j connectivity check failed: {e}")

    def execute_write(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a write transaction with parameterized Cypher query."""
        driver = self._get_driver()
        try:
            with driver.session(database=self.settings.NEO4J_DATABASE) as session:
                cypher_query = cast(LiteralString, query)
                result = session.execute_write(lambda tx: tx.run(cypher_query, parameters or {}).data())
                return result
        except (Neo4jError, Exception) as e:  # noqa: BLE001
            raise GraphDatabaseError(f"Cypher write execution failed: {e}. Query: {query}")

    def execute_read(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a read transaction with parameterized Cypher query."""
        driver = self._get_driver()
        try:
            with driver.session(database=self.settings.NEO4J_DATABASE) as session:
                cypher_query = cast(LiteralString, query)
                result = session.execute_read(lambda tx: tx.run(cypher_query, parameters or {}).data())
                return result
        except (Neo4jError, Exception) as e:  # noqa: BLE001
            raise GraphDatabaseError(f"Cypher read execution failed: {e}. Query: {query}")

    def init_schema(self):
        """Initialize database constraints and indexes."""
        logger.info("Initializing Neo4j schema constraints and indexes...")
        for query in CYPHER_CONSTRAINTS + CYPHER_INDEXES:
            try:
                self.execute_write(query)
            except (Neo4jError, Exception) as e:  # noqa: BLE001
                logger.warning(f"Error executing schema query: {e}")
