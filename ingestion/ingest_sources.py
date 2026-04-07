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
import logging
import os
from datetime import date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

from dotenv import load_dotenv

from ingestion.db import UpsertSummary, get_connection, upsert_source_assets, upsert_sources
from ingestion.excel_reader import read_sources_workbook
from ingestion.logging_utils import configure_logging, generate_run_id, log_kv
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
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging level.",
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
    overall_start = perf_counter()
    args = parse_args()
    configure_logging(args.log_level)
    logger = logging.getLogger(__name__)
    run_id = generate_run_id()
    log_kv(
        logger,
        logging.INFO,
        "script_start",
        run_id=run_id,
        script="ingest_sources",
    )
    log_kv(
        logger,
        logging.INFO,
        "cli_args",
        run_id=run_id,
        workbook=str(args.workbook),
        dry_run=args.dry_run,
        log_level=args.log_level,
    )
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")
    log_kv(
        logger,
        logging.INFO,
        "env_loaded",
        run_id=run_id,
        dotenv_path=str(repo_root / ".env"),
        database_url_configured=bool(os.getenv("DATABASE_URL")),
    )

    try:
        log_kv(
            logger,
            logging.INFO,
            "workbook_load_start",
            run_id=run_id,
            workbook=str(args.workbook),
            sheets="sources_registry,source_assets",
        )
        sources_rows, source_asset_rows = read_sources_workbook(args.workbook)
        log_kv(
            logger,
            logging.INFO,
            "workbook_load_complete",
            run_id=run_id,
            sources_rows=len(sources_rows),
            source_asset_rows=len(source_asset_rows),
        )
    except Exception as exc:
        log_kv(
            logger,
            logging.ERROR,
            "workbook_load_failed",
            run_id=run_id,
            error=str(exc),
        )
        print(f"Error reading workbook: {exc}")
        return 2

    validation_start = perf_counter()
    log_kv(logger, logging.INFO, "validation_start", run_id=run_id, sheet="sources_registry")
    valid_sources, source_errors, source_warnings = validate_sources_rows(sources_rows)
    log_kv(logger, logging.INFO, "validation_start", run_id=run_id, sheet="source_assets")
    valid_source_assets, source_asset_errors, source_asset_warnings = validate_source_assets_rows(
        source_asset_rows, valid_sources
    )
    validation_duration = perf_counter() - validation_start
    log_kv(
        logger,
        logging.INFO,
        "validation_complete",
        run_id=run_id,
        valid_sources=len(valid_sources),
        source_errors=len(source_errors),
        source_warnings=len(source_warnings),
        valid_source_assets=len(valid_source_assets),
        source_asset_errors=len(source_asset_errors),
        source_asset_warnings=len(source_asset_warnings),
        duration_seconds=f"{validation_duration:.3f}",
    )

    if source_errors or source_asset_errors:
        for message in source_errors:
            log_kv(logger, logging.ERROR, "validation_error", run_id=run_id, message=message)
        for message in source_warnings:
            log_kv(
                logger,
                logging.WARNING,
                "validation_warning",
                run_id=run_id,
                message=message,
            )
        for message in source_asset_errors:
            log_kv(logger, logging.ERROR, "validation_error", run_id=run_id, message=message)
        for message in source_asset_warnings:
            log_kv(
                logger,
                logging.WARNING,
                "validation_warning",
                run_id=run_id,
                message=message,
            )
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

    for message in source_warnings:
        log_kv(
            logger,
            logging.WARNING,
            "validation_warning",
            run_id=run_id,
            message=message,
        )
    for message in source_asset_warnings:
        log_kv(
            logger,
            logging.WARNING,
            "validation_warning",
            run_id=run_id,
            message=message,
        )
    print_messages("Source validation warnings:", source_warnings)
    print_messages("Source asset validation warnings:", source_asset_warnings)

    normalized_sources = normalize_sources_rows(valid_sources)
    normalized_source_assets = normalize_source_asset_rows(valid_source_assets)
    log_kv(
        logger,
        logging.INFO,
        "normalization_complete",
        run_id=run_id,
        normalized_sources=len(normalized_sources),
        normalized_source_assets=len(normalized_source_assets),
    )

    if args.dry_run:
        log_kv(
            logger,
            logging.INFO,
            "dry_run_enabled",
            run_id=run_id,
            message="No database writes will be performed.",
        )
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
        log_kv(
            logger,
            logging.ERROR,
            "database_config_missing",
            run_id=run_id,
            variable="DATABASE_URL",
        )
        print("Error: DATABASE_URL environment variable is not set.")
        return 2

    db_start = perf_counter()
    try:
        log_kv(logger, logging.INFO, "db_connection_start", run_id=run_id)
        with get_connection(database_url) as conn:
            log_kv(logger, logging.INFO, "transaction_start", run_id=run_id)
            with conn.transaction():
                log_kv(logger, logging.INFO, "upsert_start", run_id=run_id, table="sources")
                source_result = upsert_sources(conn, normalized_sources)
                log_kv(
                    logger,
                    logging.INFO,
                    "upsert_complete",
                    run_id=run_id,
                    table="sources",
                    inserted=source_result.inserted,
                    updated=source_result.updated,
                )
                log_kv(
                    logger,
                    logging.INFO,
                    "upsert_start",
                    run_id=run_id,
                    table="source_assets",
                )
                source_asset_result = upsert_source_assets(conn, normalized_source_assets)
                log_kv(
                    logger,
                    logging.INFO,
                    "upsert_complete",
                    run_id=run_id,
                    table="source_assets",
                    inserted=source_asset_result.inserted,
                    updated=source_asset_result.updated,
                )
            log_kv(logger, logging.INFO, "transaction_committed", run_id=run_id)
    except Exception as exc:
        log_kv(
            logger,
            logging.ERROR,
            "transaction_rolled_back",
            run_id=run_id,
            error=str(exc),
        )
        print(f"Database error during upsert: {exc}")
        return 2
    db_duration = perf_counter() - db_start
    log_kv(
        logger,
        logging.INFO,
        "db_write_complete",
        run_id=run_id,
        duration_seconds=f"{db_duration:.3f}",
    )

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
    overall_duration = perf_counter() - overall_start
    log_kv(
        logger,
        logging.INFO,
        "script_complete",
        run_id=run_id,
        duration_seconds=f"{overall_duration:.3f}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
