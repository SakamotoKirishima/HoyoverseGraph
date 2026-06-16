"""Database helpers for API endpoints.

This module provides a request-scoped psycopg connection dependency for FastAPI.
It reads ``DATABASE_URL`` from environment variables.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from psycopg import Connection, connect
from psycopg.rows import dict_row

# Load repo-root .env so DATABASE_URL is available for API runs (e.g. uvicorn).
_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / ".env")


def get_database_url() -> str:
    """Return DATABASE_URL from environment variables.

    Raises:
        RuntimeError: If DATABASE_URL is not configured.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    return database_url


def get_db_connection() -> Generator[Connection[Any], None, None]:
    """Yield a psycopg connection for one request and ensure cleanup."""
    conn = connect(get_database_url(), row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()
