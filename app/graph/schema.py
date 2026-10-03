"""Neo4j graph schema definitions, node labels, relationship types, and constraints."""

from enum import Enum


class NodeType(str, Enum):
    REPOSITORY = "Repository"
    DIRECTORY = "Directory"
    FILE = "File"
    MODULE = "Module"
    CLASS = "Class"
    FUNCTION = "Function"
    METHOD = "Method"
    PARAMETER = "Parameter"
    VARIABLE = "Variable"
    API = "API"
    API_ENDPOINT = "ApiEndpoint"
    API_CLIENT_CALL = "ApiClientCall"
    API_CONTRACT = "ApiContract"
    DOCUMENTATION = "Documentation"


class RelationType(str, Enum):
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    DEFINES = "DEFINES"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    IMPLEMENTS = "IMPLEMENTS"
    USES = "USES"
    DEPENDS_ON = "DEPENDS_ON"
    ROUTES_TO = "ROUTES_TO"
    DOCUMENTED_BY = "DOCUMENTED_BY"
    MATCHES_ENDPOINT = "MATCHES_ENDPOINT"
    MATCHES_CONTRACT = "MATCHES_CONTRACT"
    IMPLEMENTS_CONTRACT = "IMPLEMENTS_CONTRACT"
    CALLS_API = "CALLS_API"


CYPHER_CONSTRAINTS: list[str] = [
    # Constraint on Repository unique ID
    "CREATE CONSTRAINT repository_id_unique IF NOT EXISTS FOR (r:Repository) REQUIRE r.repository_id IS UNIQUE;",
    # Constraint on File unique path within repo
    "CREATE CONSTRAINT file_id_unique IF NOT EXISTS FOR (f:File) REQUIRE f.file_id IS UNIQUE;",
    # Constraint on Module unique qualified name
    "CREATE CONSTRAINT module_id_unique IF NOT EXISTS FOR (m:Module) REQUIRE m.symbol_id IS UNIQUE;",
    # Constraint on Class unique qualified name
    "CREATE CONSTRAINT class_id_unique IF NOT EXISTS FOR (c:Class) REQUIRE c.symbol_id IS UNIQUE;",
    # Constraint on Function unique symbol ID
    "CREATE CONSTRAINT function_id_unique IF NOT EXISTS FOR (fn:Function) REQUIRE fn.symbol_id IS UNIQUE;",
    # Constraint on Method unique symbol ID
    "CREATE CONSTRAINT method_id_unique IF NOT EXISTS FOR (m:Method) REQUIRE m.symbol_id IS UNIQUE;",
    # Constraint on ApiEndpoint unique endpoint_id
    "CREATE CONSTRAINT api_endpoint_id_unique IF NOT EXISTS FOR (ep:ApiEndpoint) REQUIRE ep.endpoint_id IS UNIQUE;",
    # Constraint on ApiClientCall unique call_id
    "CREATE CONSTRAINT api_client_call_id_unique IF NOT EXISTS FOR (call:ApiClientCall) REQUIRE call.call_id IS UNIQUE;",
    # Constraint on ApiContract unique contract_id
    "CREATE CONSTRAINT api_contract_id_unique IF NOT EXISTS FOR (c:ApiContract) REQUIRE c.contract_id IS UNIQUE;",
]

CYPHER_INDEXES: list[str] = [
    "CREATE INDEX symbol_qualified_name_idx IF NOT EXISTS FOR (n:Class) ON (n.qualified_name);",
    "CREATE INDEX function_qualified_name_idx IF NOT EXISTS FOR (n:Function) ON (n.qualified_name);",
    "CREATE INDEX method_qualified_name_idx IF NOT EXISTS FOR (n:Method) ON (n.qualified_name);",
    "CREATE INDEX symbol_name_idx IF NOT EXISTS FOR (n:Function) ON (n.name);",
    "CREATE INDEX api_endpoint_path_idx IF NOT EXISTS FOR (ep:ApiEndpoint) ON (ep.path);",
    "CREATE INDEX api_client_url_idx IF NOT EXISTS FOR (call:ApiClientCall) ON (call.url);",
]
