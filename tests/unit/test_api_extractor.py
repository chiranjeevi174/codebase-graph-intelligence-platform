"""Unit tests for API extractor."""

from app.models.entities import SourceFile
from app.parsing.api_extractor import APIExtractor


def test_api_extractor_python_and_openapi():
    extractor = APIExtractor()

    # 1. Python FastAPI
    py_file = SourceFile(
        file_path="/repo/app.py",
        relative_path="app.py",
        language="python",
        extension=".py",
    )
    py_code = """
from fastapi import FastAPI
app = FastAPI()

@app.get("/api/users")
def get_users():
    return []
"""
    endpoints, _client_calls, contracts = extractor.extract_from_content(py_file, py_code, "test_repo")
    assert len(endpoints) == 1
    assert endpoints[0].http_method == "GET"
    assert endpoints[0].path == "/api/users"
    assert endpoints[0].framework == "FastAPI"

    # 2. OpenAPI YAML
    yaml_file = SourceFile(
        file_path="/repo/openapi.yaml",
        relative_path="openapi.yaml",
        language="yaml",
        extension=".yaml",
    )
    yaml_code = """
openapi: 3.0.0
paths:
  /api/users:
    get:
      operationId: getUsers
      summary: Get users
"""
    _endpoints, _client_calls, contracts = extractor.extract_from_content(yaml_file, yaml_code, "test_repo")
    assert len(contracts) == 1
    assert contracts[0].http_method == "GET"
    assert contracts[0].path_template == "/api/users"
    assert contracts[0].operation_id == "getUsers"


def test_api_extractor_typescript_client_calls():
    extractor = APIExtractor()
    ts_file = SourceFile(
        file_path="/repo/api.ts",
        relative_path="api.ts",
        language="typescript",
        extension=".ts",
    )
    ts_code = """
export async function getUsers() {
    const res = await fetch("/api/users");
    return res.json();
}
export async function postUser(data: any) {
    return axios.post("/api/users", data);
}
"""
    _endpoints, client_calls, _contracts = extractor.extract_from_content(ts_file, ts_code, "test_repo")
    assert len(client_calls) == 2
    methods = {c.http_method for c in client_calls}
    urls = {c.url for c in client_calls}
    assert "GET" in methods
    assert "POST" in methods
    assert "/api/users" in urls


def test_api_extractor_fastapi_prefix_and_multiline(tmp_path):
    extractor = APIExtractor()

    # Create a router file and a route file
    repo_dir = tmp_path / "app"
    repo_dir.mkdir(parents=True)
    router_file = repo_dir / "router.py"
    router_file.write_text(
        'from fastapi import APIRouter\napi_router = APIRouter(prefix="/api/v1")\n',
        encoding="utf-8",
    )

    incidents_file = repo_dir / "incidents.py"
    code = '''
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/incidents")

class IncidentCreate(BaseModel):
    title: str

class IncidentResponse(BaseModel):
    id: str

@router.post(
    "",
    response_model=IncidentResponse,
)
async def create_incident(data: IncidentCreate):
    return {"id": "1"}
'''
    incidents_file.write_text(code, encoding="utf-8")

    sf = SourceFile(
        file_path=str(incidents_file),
        relative_path="app/incidents.py",
        language="python",
        extension=".py",
    )

    endpoints, _, _ = extractor.extract_from_content(sf, code, "test_repo")
    assert len(endpoints) == 1
    ep = endpoints[0]
    assert ep.http_method == "POST"
    assert ep.path == "/api/v1/incidents"
    assert ep.request_schema == "IncidentCreate"
    assert ep.response_schema == "IncidentResponse"
    assert ep.controller_symbol.endswith("create_incident")

