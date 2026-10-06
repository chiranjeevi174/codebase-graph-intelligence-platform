"""Structured logging configuration for Codebase Graph Intelligence Platform."""

import logging
import sys
from typing import ClassVar


class SensitiveDataFilter(logging.Filter):
    """Filter that masks sensitive keys or tokens in log outputs."""

    SENSITIVE_PATTERNS: ClassVar[list[str]] = ["api_key", "password", "secret", "token", "authorization"]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._sanitize(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(self._sanitize(str(arg)) for arg in record.args)
        elif isinstance(record.args, dict):
            record.args = {
                k: self._sanitize(str(v)) if any(s in k.lower() for s in self.SENSITIVE_PATTERNS) else v
                for k, v in record.args.items()
            }
        return True

    def _sanitize(self, text: str) -> str:
        # Simple heuristic to avoid printing API keys / passwords in log messages
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern in text.lower() and "=" in text:
                parts = text.split("=")
                if len(parts) == 2 and len(parts[1].strip()) > 4:
                    text = f"{parts[0]}=[REDACTED]"
        return text


import json


class JSONFormatter(logging.Formatter):
    """JSON log record formatter for production observability."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "filename": record.filename,
            "lineno": record.lineno,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id is not None:
            log_obj["request_id"] = request_id
        job_id = getattr(record, "job_id", None)
        if job_id is not None:
            log_obj["job_id"] = job_id
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_logger(name: str = "codebase_graph", level: str = "INFO", log_format: str = "text") -> logging.Logger:
    """Configure and return a structured logger instance."""
    logger = logging.getLogger(name)
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)

        if log_format.lower() == "json":
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s:%(filename)s:%(lineno)d] - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        console_handler.setFormatter(formatter)
        console_handler.addFilter(SensitiveDataFilter())

        logger.addHandler(console_handler)

    return logger


logger = setup_logger()
