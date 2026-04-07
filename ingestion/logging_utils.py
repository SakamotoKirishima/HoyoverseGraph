"""Shared structured logging helpers for ingestion scripts.

Usage:
    from ingestion.logging_utils import configure_logging, generate_run_id, log_kv

    configure_logging("INFO")
    logger = logging.getLogger(__name__)
    run_id = generate_run_id()
    log_kv(logger, logging.INFO, "ingestion_started", run_id=run_id, workbook="file.xlsx")
"""

from __future__ import annotations

import logging
from uuid import uuid4

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


def parse_log_level(level: str) -> int:
    """Parse CLI log level safely.

    Args:
        level: User-provided log level string.

    Returns:
        Logging module integer level.

    Raises:
        ValueError: If level is not one of DEBUG/INFO/WARNING/ERROR.
    """
    normalized = level.strip().upper()
    if normalized not in ALLOWED_LOG_LEVELS:
        allowed = ", ".join(sorted(ALLOWED_LOG_LEVELS))
        raise ValueError(f"Invalid log level '{level}'. Allowed values: {allowed}.")
    return getattr(logging, normalized)


def configure_logging(level: str = "INFO") -> int:
    """Configure process-wide logging for ingestion scripts.

    Args:
        level: One of DEBUG/INFO/WARNING/ERROR.

    Returns:
        Parsed integer log level.
    """
    parsed_level = parse_log_level(level)
    logging.basicConfig(level=parsed_level, format=LOG_FORMAT, force=True)
    return parsed_level


def generate_run_id() -> str:
    """Generate a short run ID for correlating logs for one ingestion run."""
    return uuid4().hex[:12]


def log_kv(logger: logging.Logger, level: int, event: str, **fields: object) -> None:
    """Log a structured event as key=value message.

    Args:
        logger: Module logger.
        level: Logging level constant from logging module.
        event: Event name.
        **fields: Key-value fields to include.
    """
    parts = [f"event={event}"]
    for key, value in fields.items():
        text = str(value).replace("\n", " ").strip()
        parts.append(f"{key}={text!r}")
    logger.log(level, " ".join(parts))
