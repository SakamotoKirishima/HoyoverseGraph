"""CLI ingestion step for sources_registry + source_assets.

Usage:
    python -m ingestion.ingest_sources --workbook path/to/file.xlsx
    python -m ingestion.ingest_sources --workbook path/to/file.xlsx --dry-run

Flow:
1. Read ``sources_registry`` and ``source_assets`` from workbook
2. Validate sources
3. Validate source_assets against valid source rows
4. On validation success, upsert both tables in one DB transaction
"""

from __future__ import annotations

import argparse
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

from dotenv import load_dotenv

from ingestion.db import UpsertSummary, get_connection, upsert_source_assets, upsert_sources
from ingestion.excel_reader import read_sources_workbook
from ingestion.validators import validate_source_assets_rows, validate_sources_rows


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for sources ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest sources_registry and source_assets from workbook into PostgreSQL."
    )
    parser.add_argument(
        "--workbook",
        required=True,
        type=Path,
        help="Path to workbook (.xlsx/.xlsm).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read + validate only, skip DB writes.",
    )
    return parser.parse_args()


def _empty_to_none(value: Any) -> Any:
    """Convert blank strings to None."""
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _parse_publication_date(value: Any) -> date | None:
    """Convert publication_date to date when present and parseable."""
    value = _empty_to_none(value)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y/%m", "%m/%d/%Y", "%Y"):
            try:
                parsed = datetime.strptime(text, fmt)
                if fmt in ("%Y-%m", "%Y/%m"):
                    return date(parsed.year, parsed.month, 1)
                if fmt == "%Y":
                    return date(parsed.year, 1, 1)
                return parsed.date()
            except ValueError:
                continue
    return None


def normalize_sources_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Normalize validated source rows for DB upsert."""
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        row_copy = {k: _empty_to_none(v) for k, v in dict(row).items()}
        row_copy["publication_date"] = _parse_publication_date(
            row_copy.get("publication_date")
        )
        normalized_rows.append(row_copy)
    return normalized_rows


def normalize_source_asset_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Normalize validated source asset rows for DB upsert."""
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        row_copy = {k: _empty_to_none(v) for k, v in dict(row).items()}
        normalized_rows.append(row_copy)
    return normalized_rows


def print_messages(title: str, messages: list[str]) -> None:
    """Print a labelled message list."""
    if not messages:
        return
    print(title)
    for message in messages:
        print(f"- {message}")


def print_summary(
    *,
    source_rows_read: int,
    source_valid_rows: int,
    source_warnings: int,
    source_result: UpsertSummary,
    source_asset_rows_read: int,
    source_asset_valid_rows: int,
    source_asset_warnings: int,
    source_asset_result: UpsertSummary,
    dry_run: bool,
) -> None:
    """Print ingestion summary."""
    print(
        "Summary: "
        f"source_rows_read={source_rows_read} "
        f"source_valid_rows={source_valid_rows} "
        f"source_warnings={source_warnings} "
        f"source_inserted={source_result.inserted} "
        f"source_updated={source_result.updated} "
        f"source_asset_rows_read={source_asset_rows_read} "
        f"source_asset_valid_rows={source_asset_valid_rows} "
        f"source_asset_warnings={source_asset_warnings} "
        f"source_asset_inserted={source_asset_result.inserted} "
        f"source_asset_updated={source_asset_result.updated} "
        f"dry_run={dry_run}"
    )


def main() -> int:
    """Run sources + source_assets ingestion pipeline.

    Exit codes:
    - 0: success
    - 1: validation failed
    - 2: runtime/config/read/write error
    """
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")

    try:
        sources_rows, source_asset_rows = read_sources_workbook(args.workbook)
    except Exception as exc:
        print(f"Error reading workbook: {exc}")
        return 2

    valid_sources, source_errors, source_warnings = validate_sources_rows(sources_rows)
    valid_source_assets, source_asset_errors, source_asset_warnings = validate_source_assets_rows(
        source_asset_rows, valid_sources
    )

    if source_errors or source_asset_errors:
        print_messages("Source validation errors:", source_errors)
        print_messages("Source validation warnings:", source_warnings)
        print_messages("Source asset validation errors:", source_asset_errors)
        print_messages("Source asset validation warnings:", source_asset_warnings)
        print_summary(
            source_rows_read=len(sources_rows),
            source_valid_rows=len(valid_sources),
            source_warnings=len(source_warnings),
            source_result=UpsertSummary(inserted=0, updated=0),
            source_asset_rows_read=len(source_asset_rows),
            source_asset_valid_rows=len(valid_source_assets),
            source_asset_warnings=len(source_asset_warnings),
            source_asset_result=UpsertSummary(inserted=0, updated=0),
            dry_run=args.dry_run,
        )
        return 1

    print_messages("Source validation warnings:", source_warnings)
    print_messages("Source asset validation warnings:", source_asset_warnings)

    normalized_sources = normalize_sources_rows(valid_sources)
    normalized_source_assets = normalize_source_asset_rows(valid_source_assets)

    if args.dry_run:
        print_summary(
            source_rows_read=len(sources_rows),
            source_valid_rows=len(valid_sources),
            source_warnings=len(source_warnings),
            source_result=UpsertSummary(inserted=0, updated=0),
            source_asset_rows_read=len(source_asset_rows),
            source_asset_valid_rows=len(valid_source_assets),
            source_asset_warnings=len(source_asset_warnings),
            source_asset_result=UpsertSummary(inserted=0, updated=0),
            dry_run=True,
        )
        return 0

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL environment variable is not set.")
        return 2

    try:
        with get_connection(database_url) as conn:
            with conn.transaction():
                source_result = upsert_sources(conn, normalized_sources)
                source_asset_result = upsert_source_assets(conn, normalized_source_assets)
    except Exception as exc:
        print(f"Database error during upsert: {exc}")
        return 2

    print_summary(
        source_rows_read=len(sources_rows),
        source_valid_rows=len(valid_sources),
        source_warnings=len(source_warnings),
        source_result=source_result,
        source_asset_rows_read=len(source_asset_rows),
        source_asset_valid_rows=len(valid_source_assets),
        source_asset_warnings=len(source_asset_warnings),
        source_asset_result=source_asset_result,
        dry_run=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
