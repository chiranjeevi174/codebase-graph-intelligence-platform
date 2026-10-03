"""FastAPI production middleware for Request Correlation, Rate Limiting, Metrics, and Error Sanitization."""

import time
import uuid
from collections import defaultdict
from typing import Any

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import get_settings
from app.utils.logger import logger


# Simple in-memory metrics registry
class ApplicationMetricsRegistry:
    """In-memory metrics tracker for request latency, status counts, and retrieval timing."""

    def __init__(self):
        self.request_count: int = 0
        self.error_count: int = 0
        self.status_codes: dict[int, int] = defaultdict(int)
        self.total_latency_ms: float = 0.0
        self.endpoint_latency_ms: dict[str, float] = defaultdict(float)
        self.endpoint_calls: dict[str, int] = defaultdict(int)

    def record_request(self, path: str, status_code: int, duration_ms: float):
        self.request_count += 1
        self.status_codes[status_code] += 1
        if status_code >= 400:
            self.error_count += 1
        self.total_latency_ms += duration_ms
        self.endpoint_latency_ms[path] += duration_ms
        self.endpoint_calls[path] += 1

    def get_summary(self) -> dict[str, Any]:
        avg_latency = round(self.total_latency_ms / max(1, self.request_count), 2)
        endpoint_averages = {
            ep: round(self.endpoint_latency_ms[ep] / max(1, self.endpoint_calls[ep]), 2)
            for ep in self.endpoint_calls
        }
        return {
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "average_latency_ms": avg_latency,
            "status_code_distribution": dict(self.status_codes),
            "endpoints": endpoint_averages,
        }


metrics_registry = ApplicationMetricsRegistry()


class ProductionHardeningMiddleware(BaseHTTPMiddleware):
    """Production hardening middleware handling correlation IDs, rate limits, metrics, and safe errors."""

    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        # Rate limiting window tracker: ip -> list of timestamps
        self._rate_limits: dict[str, list[float]] = defaultdict(list)

    def _check_rate_limit(self, client_ip: str) -> bool:
        now = time.time()
        window = 60.0  # 1 minute window
        limit = self.settings.RATE_LIMIT_PER_MINUTE

        # Clean old timestamps
        timestamps = [ts for ts in self._rate_limits[client_ip] if now - ts < window]
        self._rate_limits[client_ip] = timestamps

        if len(timestamps) >= limit:
            return False

        self._rate_limits[client_ip].append(now)
        return True

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        # 1. Request Correlation ID
        req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = req_id

        # 2. Rate Limiting Check (Skip metrics / health endpoints)
        path = request.url.path
        if not path.startswith(("/health", "/live", "/ready", "/metrics", "/docs", "/openapi.json")):
            client_ip = request.client.host if request.client else "unknown"
            if not self._check_rate_limit(client_ip):
                logger.warning(f"[RateLimitExceeded] Client '{client_ip}' exceeded limit on path '{path}' (Request ID: {req_id}).")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate Limit Exceeded",
                        "code": "RATE_LIMIT_EXCEEDED",
                        "request_id": req_id,
                        "detail": f"Allowed rate of {self.settings.RATE_LIMIT_PER_MINUTE} requests/min exceeded. Please slow down.",
                    },
                    headers={"X-Request-ID": req_id},
                )

        # 3. Request Execution & Error Sanitization
        try:
            response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 2)
            metrics_registry.record_request(path, response.status_code, duration_ms)
            response.headers["X-Request-ID"] = req_id
            return response
        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            metrics_registry.record_request(path, 500, duration_ms)
            err_msg = str(exc)
            logger.error(f"[UnhandledException] Error handling {request.method} {path} (ID: {req_id}): {err_msg}")

            # Sanitized response
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "code": "INTERNAL_SERVER_ERROR",
                    "request_id": req_id,
                    "detail": "An internal error occurred while processing your request.",
                },
                headers={"X-Request-ID": req_id},
            )
