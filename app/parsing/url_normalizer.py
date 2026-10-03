"""Centralized HTTP Method and API URL path normalization utilities."""

import re

VALID_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}


def normalize_http_method(method: str | None) -> str:
    """Normalize HTTP method string to uppercase standard representation.

    Args:
        method: Method string e.g. 'get', 'POST', 'Fetch'.

    Returns:
        Canonical uppercase HTTP method e.g. 'GET', 'POST', or 'UNKNOWN'.
    """
    if not method:
        return "GET"
    clean = method.strip().upper()
    if clean in VALID_HTTP_METHODS:
        return clean
    return "UNKNOWN"


def normalize_url_path(url: str, base_url: str = "") -> str:
    """Normalize API path by combining base URL, stripping domain/protocol, and removing query strings.

    Args:
        url: URL string e.g. 'http://localhost:8080/api/users?page=1#section'.
        base_url: Optional base path e.g. '/api'.

    Returns:
        Normalized relative URL path starting with '/' e.g. '/api/users'.
    """
    if not url:
        return "/"

    clean = url.strip()

    # 1. Strip protocol & domain if full URL e.g. http://localhost:8080/api/users -> /api/users
    if "://" in clean:
        clean = "/" + clean.split("://", 1)[-1].split("/", 1)[-1]

    # 2. Strip query string and fragment
    clean = clean.split("?", 1)[0].split("#", 1)[0]

    # 3. Prepend base_url if provided and path is relative
    if base_url:
        b_clean = base_url.strip().rstrip("/")
        if not b_clean.startswith("/"):
            b_clean = "/" + b_clean
        if not clean.startswith(b_clean):
            clean = f"{b_clean}/{clean.lstrip('/')}"

    # 4. Clean consecutive slashes
    clean = re.sub(r"/+", "/", clean)

    # 5. Strip trailing slash unless root '/'
    if len(clean) > 1 and clean.endswith("/"):
        clean = clean.rstrip("/")

    if not clean.startswith("/"):
        clean = "/" + clean

    return clean


def extract_route_template(url_path: str) -> str:
    """Convert path variables into normalized template placeholder '{param}'.

    Examples:
        '/api/users/123' -> '/api/users/{param}'
        '/api/users/{id}' -> '/api/users/{param}'
        '/api/users/:id' -> '/api/users/{param}'
    """
    path = normalize_url_path(url_path)

    # 1. Replace explicit path parameters e.g. {id}, {userId}, :id
    path = re.sub(r"\{[^}]+\}", "{param}", path)
    path = re.sub(r"/:[a-zA-Z0-9_]+", "/{param}", path)

    # 2. Replace numeric IDs e.g. /123, /999
    path = re.sub(r"/\d+(?=/|$)", "/{param}", path)

    # 3. Replace UUID strings e.g. /123e4567-e89b-12d3-a456-426614174000
    path = re.sub(r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?=/|$)", "/{param}", path)

    return path


def match_urls(
    client_url: str,
    client_method: str,
    endpoint_path: str,
    endpoint_method: str,
) -> tuple[bool, str]:
    """Determine if a client call matches an endpoint route and return the match reason.

    Returns:
        (is_match: bool, match_reason: str)
    """
    c_m = normalize_http_method(client_method)
    e_m = normalize_http_method(endpoint_method)

    # Method check (if both methods are known and distinct, no match)
    if c_m != "UNKNOWN" and e_m != "UNKNOWN" and c_m != e_m:
        return False, "METHOD_MISMATCH"

    c_path = normalize_url_path(client_url)
    e_path = normalize_url_path(endpoint_path)

    # 1. Exact path match
    if c_path == e_path:
        return True, "EXACT_METHOD_AND_PATH"

    # 2. Route template match
    c_tmpl = extract_route_template(c_path)
    e_tmpl = extract_route_template(e_path)
    if c_tmpl == e_tmpl:
        return True, "PATH_TEMPLATE_MATCH"

    # 3. Base URL / suffix match e.g. /users vs /api/users
    c_base = c_path.split("/")[-1]
    e_base = e_path.split("/")[-1]
    if c_path.endswith(e_path) or e_path.endswith(c_path):
        return True, "BASE_URL_PLUS_PATH"

    return False, "NO_MATCH"
