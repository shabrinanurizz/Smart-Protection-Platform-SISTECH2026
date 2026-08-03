"""
JSONL logger untuk request, prediction, dan error logging.

Log disimpan dalam format JSON Lines (JSONL):
  logs/requests.jsonl
  logs/predictions.jsonl
  logs/errors.jsonl

API key / secret JANGAN pernah ditulis ke log.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from apps.bootstrap.config import LOG_CONFIG


# Fields that must never appear in logs
_SENSITIVE_KEYS = frozenset(
    {
        "routing_api_key",
        "api_key",
        "secret",
        "password",
        "token",
        "authorization",
        "x-api-key",
    }
)


def _redact(value: Any) -> Any:
    """Redact sensitive values in a dict recursively."""
    if isinstance(value, dict):
        return {k: ("***REDACTED***" if k.lower() in _SENSITIVE_KEYS else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _write_log(log_path: str, entry: Dict[str, Any]) -> None:
    """Write a single JSON entry to a JSONL file."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    # Redact sensitive data before writing
    safe_entry = _redact(entry)
    line = json.dumps(safe_entry, default=str)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_request(
    method: str,
    path: str,
    status_code: int,
    request_body: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> None:
    """Log an incoming HTTP request."""
    entry = {
        "timestamp": _now_iso(),
        "type": "request",
        "method": method,
        "path": path,
        "status_code": status_code,
        "request_id": request_id,
        "duration_ms": duration_ms,
        "request_body": request_body or {},
    }
    log_path = LOG_CONFIG.get("requests_log", "logs/requests.jsonl")
    _write_log(log_path, entry)


def log_prediction(
    risk_score: float,
    risk_level: str,
    input_features: Dict[str, Any],
    request_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a model prediction."""
    entry = {
        "timestamp": _now_iso(),
        "type": "prediction",
        "risk_score": risk_score,
        "risk_level": risk_level,
        "request_id": request_id,
        "input": input_features,
        "extra": extra or {},
    }
    log_path = LOG_CONFIG.get("predictions_log", "logs/predictions.jsonl")
    _write_log(log_path, entry)


def log_error(
    error_type: str,
    message: str,
    path: Optional[str] = None,
    request_id: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """Log an error."""
    entry = {
        "timestamp": _now_iso(),
        "type": "error",
        "error_type": error_type,
        "message": message,
        "path": path,
        "request_id": request_id,
        "detail": detail or {},
    }
    log_path = LOG_CONFIG.get("errors_log", "logs/errors.jsonl")
    _write_log(log_path, entry)
