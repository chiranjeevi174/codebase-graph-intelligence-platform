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
