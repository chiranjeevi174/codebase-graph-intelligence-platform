"""Unit tests for API route and contract matcher."""

from app.models.entities import ApiClientCall, ApiContract, ApiEndpoint
from app.parsing.api_matcher import APIMatcher


def test_api_matcher_client_endpoint_contract():
    matcher = APIMatcher()

    endpoint = ApiEndpoint(
        endpoint_id="ep_1",
        repository_id="repo",
        file_path="UserController.java",
        language="java",
        http_method="GET",
        path="/api/users",
        controller_symbol="UserController.getUsers",
        qualified_name="GET:/api/users",
        framework="Spring",
    )

    client_call = ApiClientCall(
        call_id="call_1",
        repository_id="repo",
        file_path="api.ts",
        language="typescript",
        http_method="GET",
        url="/api/users",
        client_symbol="fetchUsers",
    )

    contract = ApiContract(
        contract_id="contract_1",
        repository_id="repo",
        file_path="openapi.yaml",
        operation_id="getUsers",
        http_method="GET",
        path_template="/api/users",
    )

    matches = matcher.match_api_elements(
        endpoints=[endpoint],
        client_calls=[client_call],
        contracts=[contract],
    )

    assert len(matches) >= 3
    match_reasons = {m.match_reason for m in matches}
    assert "EXACT_METHOD_AND_PATH" in match_reasons
    assert "IMPLEMENTS_CONTRACT" in match_reasons
    assert "MATCHES_CONTRACT" in match_reasons
