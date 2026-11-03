"""Structured standard-library logging for job applications and workers."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import TextIO

_CONTEXT_FIELDS = (
    "worker_event",
    "worker_id",
    "job_id",
    "run_id",
    "job_template",
    "job_attempt",
    "otel_trace_id",
    "otel_span_id",
)


class JsonLogFormatter(logging.Formatter):
    """Render stable JSON Lines with worker and trace correlation fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for name in _CONTEXT_FIELDS:
            value = getattr(record, name, None)
            if value not in {None, "", 0}:
                payload[name] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_job_logging(
    *,
    level: int | str = logging.INFO,
    json_output: bool = False,
    stream: TextIO | None = None,
) -> logging.Logger:
    """Configure the ``pyfetcher`` logger without mutating the root logger."""
    package_logger = logging.getLogger("pyfetcher")
    package_logger.setLevel(level)
    package_logger.propagate = False
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(
        JsonLogFormatter()
        if json_output
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    package_logger.handlers.clear()
    package_logger.addHandler(handler)
    return package_logger


__all__ = ["JsonLogFormatter", "configure_job_logging"]
