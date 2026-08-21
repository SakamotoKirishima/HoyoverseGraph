"""Configuration helpers for environment-backed API settings."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / ".env")

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def parse_allowed_origins(raw_value: str | None) -> list[str]:
    """Parse a comma-separated origin list into normalized values."""
    if raw_value is None:
        return list(DEFAULT_ALLOWED_ORIGINS)

    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


def get_allowed_origins() -> list[str]:
    """Return configured CORS origins from ALLOWED_ORIGINS or local defaults."""
    return parse_allowed_origins(os.getenv("ALLOWED_ORIGINS"))
