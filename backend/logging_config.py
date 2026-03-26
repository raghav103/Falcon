"""
Structured logging configuration for Falcon backend.

Sets up logging with appropriate format based on environment.
Production uses JSON format for log aggregation, development uses human-readable format.
"""

import logging
import sys
import json
from typing import Any


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for production log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra"):
            log_data.update(record.extra)

        return json.dumps(log_data)


def setup_logging(log_level: str = "INFO", environment: str = "development") -> logging.Logger:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        environment: Environment name (development or production)

    Returns:
        Root logger for the Falcon application
    """
    # Determine format based on environment
    if environment == "production":
        formatter = JSONFormatter()
    else:
        # Human-readable format for development
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    # Configure root handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.addHandler(handler)

    # Suppress noisy third-party logs
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Get Falcon app logger
    logger = logging.getLogger("falcon")
    logger.info(f"Logging configured: level={log_level}, environment={environment}")

    return logger
