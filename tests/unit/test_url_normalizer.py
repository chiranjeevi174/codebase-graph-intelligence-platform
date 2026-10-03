"""Unit tests for URL and HTTP method normalizers."""

from app.parsing.url_normalizer import (
    extract_route_template,
    match_urls,
    normalize_http_method,
    normalize_url_path,
)


def test_normalize_http_method():
    assert normalize_http_method("get") == "GET"
    assert normalize_http_method("POST") == "POST"
    assert normalize_http_method("fetch") == "UNKNOWN"
    assert normalize_http_method(None) == "GET"


def test_normalize_url_path():
    assert normalize_url_path("http://localhost:8080/api/users?page=1#head") == "/api/users"
    assert normalize_url_path("/api/users/") == "/api/users"
    assert normalize_url_path("users", base_url="/api") == "/api/users"
    assert normalize_url_path("/api/users//123") == "/api/users/123"


def test_extract_route_template():
    assert extract_route_template("/api/users/123") == "/api/users/{param}"
    assert extract_route_template("/api/users/{id}") == "/api/users/{param}"
    assert extract_route_template("/api/users/:id") == "/api/users/{param}"


def test_match_urls_exact_and_template():
    # Exact match
    matched, reason = match_urls("/api/users", "GET", "/api/users", "GET")
    assert matched is True
    assert reason == "EXACT_METHOD_AND_PATH"

    # Template match
    matched, reason = match_urls("/api/users/123", "GET", "/api/users/{id}", "GET")
    assert matched is True
    assert reason == "PATH_TEMPLATE_MATCH"

    # Method mismatch
    matched, _ = match_urls("/api/users", "GET", "/api/users", "POST")
    assert matched is False
