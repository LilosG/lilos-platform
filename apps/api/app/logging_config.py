"""Structured JSON logging configuration for the API process."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from apps.api.app.config import Settings
from apps.api.app.context import current_correlation_id

APPLICATION_LOGGER_NAME = "lilos"


class JsonFormatter(logging.Formatter):
    """Serialize application log records as one JSON object per line."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.environment = settings.environment.value
        self.version = settings.api_version

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "severity": record.levelname,
            "environment": self.environment,
            "service": "lilos-api",
            "deployment_version": self.version,
            "event_name": getattr(record, "event_name", record.getMessage()),
            "message": record.getMessage(),
            "correlation_id": getattr(
                record,
                "correlation_id",
                current_correlation_id(),
            ),
        }
        for field_name in (
            "method",
            "route",
            "status_code",
            "duration_ms",
            "outcome",
            "normalized_error_code",
            "exception_type",
            "platform_user_id",
            "assurance_level",
            "organization_id",
            "permission_key",
            "resource_scope",
            "minimum_assurance_level",
        ):
            value = getattr(record, field_name, None)
            if value is not None:
                payload[field_name] = value
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def configure_logging(settings: Settings) -> None:
    """Configure the LILOs application logger without changing third-party loggers."""
    logger = logging.getLogger(APPLICATION_LOGGER_NAME)
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(settings))
    logger.addHandler(handler)
    logger.setLevel(settings.log_level.value)
    logger.propagate = False
