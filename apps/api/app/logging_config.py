"""Structured JSON logging configuration for the API process."""

import json
import logging
from datetime import UTC, datetime
from typing import Any, Final

from apps.api.app.config import Settings
from apps.api.app.context import current_correlation_id
from apps.api.app.observability.telemetry import redact

APPLICATION_LOGGER_NAME = "lilos"

_RESERVED_FIELDS: Final = frozenset(
    {
        "timestamp",
        "severity",
        "environment",
        "service",
        "deployment_version",
        "release",
        "event_name",
        "message",
        "correlation_id",
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Serialize application log records as one JSON object per line."""

    def __init__(self, settings: Settings, service_name: str = "lilos-api") -> None:
        super().__init__()
        self.environment = settings.environment.value
        self.version = settings.api_version
        self.release = settings.release
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "severity": record.levelname,
            "environment": self.environment,
            "service": self.service_name,
            "deployment_version": self.version,
            "release": self.release,
            "event_name": getattr(record, "event_name", record.getMessage()),
            "message": record.getMessage(),
            "correlation_id": getattr(
                record,
                "correlation_id",
                current_correlation_id(),
            ),
        }
        for field_name, value in record.__dict__.items():
            if field_name in _RESERVED_FIELDS or value is None:
                continue
            payload[field_name] = value
        return json.dumps(redact(payload), separators=(",", ":"), ensure_ascii=True)


def configure_logging(settings: Settings, service_name: str = "lilos-api") -> None:
    """Configure the LILOs application logger without changing third-party loggers."""
    logger = logging.getLogger(APPLICATION_LOGGER_NAME)
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(settings, service_name))
    logger.addHandler(handler)
    logger.setLevel(settings.log_level.value)
    logger.propagate = False
