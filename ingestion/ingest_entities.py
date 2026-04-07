"""CLI ingestion step for entities_seed -> PostgreSQL entities."""

from __future__ import annotations

import argparse
import logging
import os
from time import perf_counter
from pathlib import Path
from typing import Any, Mapping

from dotenv import load_dotenv

from ingestion.db import UpsertSummary, get_connection, upsert_entities
from ingestion.excel_reader import read_entities_workbook
from ingestion.logging_utils import configure_logging, generate_run_id, log_kv
from ingestion.validators import validate_entities_rows

PRIMARY_SCOPE_GAME_ALIASES: dict[str, str] = {
    "HI3": "Honkai Impact 3",
    "Honkai Impact 3rd": "Honkai Impact 3",
    "HSR": "Honkai: Star Rail",
    "Genshin": "Genshin Impact",
    "GGZ": "Gun Girls Z",
    "Guns Girl Z": "Gun Girls Z",
    "Cross-title": "Multi",
}


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Ingest entities_seed from workbook into PostgreSQL."
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
        help="Validate and normalize only, skip DB writes.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging level.",
    )
    return parser.parse_args()


def _normalize_primary_scope_game(value: Any) -> Any:
    """Normalize primary_scope_game aliases."""
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped == "":
        return None
    return PRIMARY_SCOPE_GAME_ALIASES.get(stripped, stripped)


def normalize_entity_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Normalize validated entity rows before persistence."""
    normalized: list[dict[str, Any]] = []
    for row in rows:
        row_copy = dict(row)
        row_copy["primary_scope_game"] = _normalize_primary_scope_game(
            row_copy.get("primary_scope_game")
        )
        normalized.append(row_copy)
    return normalized


def print_messages(title: str, messages: list[str]) -> None:
    """Print a labelled list of messages."""
    if not messages:
        return
    print(title)
    for message in messages:
        print(f"- {message}")


def print_summary(
    *,
    rows_read: int,
    valid_rows: int,
    warnings_count: int,
    result: UpsertSummary,
    dry_run: bool,
) -> None:
    """Print final ingestion summary."""
    print(
        "Summary: "
        f"rows_read={rows_read} "
        f"valid_rows={valid_rows} "
        f"warnings={warnings_count} "
        f"inserted={result.inserted} "
        f"updated={result.updated} "
        f"dry_run={dry_run}"
    )


def main() -> int:
    """Run entities ingestion pipeline step."""
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
        script="ingest_entities",
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
            sheets="entities_seed,entity_types",
        )
        entities_rows, entity_type_rows = read_entities_workbook(args.workbook)
        log_kv(
            logger,
            logging.INFO,
            "workbook_load_complete",
            run_id=run_id,
            entities_rows=len(entities_rows),
            entity_type_rows=len(entity_type_rows),
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
    log_kv(logger, logging.INFO, "validation_start", run_id=run_id, sheet="entities_seed")
    valid_rows, errors, warnings = validate_entities_rows(entities_rows, entity_type_rows)
    validation_duration = perf_counter() - validation_start
    log_kv(
        logger,
        logging.INFO,
        "validation_complete",
        run_id=run_id,
        valid_rows=len(valid_rows),
        errors=len(errors),
        warnings=len(warnings),
        duration_seconds=f"{validation_duration:.3f}",
    )

    if errors:
        for message in errors:
            log_kv(logger, logging.ERROR, "validation_error", run_id=run_id, message=message)
        for message in warnings:
            log_kv(
                logger,
                logging.WARNING,
                "validation_warning",
                run_id=run_id,
                message=message,
            )
        print_messages("Validation errors:", errors)
        print_messages("Validation warnings:", warnings)
        print_summary(
            rows_read=len(entities_rows),
            valid_rows=len(valid_rows),
            warnings_count=len(warnings),
            result=UpsertSummary(inserted=0, updated=0),
            dry_run=args.dry_run,
        )
        return 1

    if warnings:
        for message in warnings:
            log_kv(
                logger,
                logging.WARNING,
                "validation_warning",
                run_id=run_id,
                message=message,
            )
        print_messages("Validation warnings:", warnings)

    normalized_rows = normalize_entity_rows(valid_rows)
    log_kv(
        logger,
        logging.INFO,
        "normalization_complete",
        run_id=run_id,
        normalized_rows=len(normalized_rows),
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
            rows_read=len(entities_rows),
            valid_rows=len(valid_rows),
            warnings_count=len(warnings),
            result=UpsertSummary(inserted=0, updated=0),
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
                log_kv(logger, logging.INFO, "upsert_start", run_id=run_id, table="entities")
                result = upsert_entities(conn, normalized_rows)
                log_kv(
                    logger,
                    logging.INFO,
                    "upsert_complete",
                    run_id=run_id,
                    table="entities",
                    inserted=result.inserted,
                    updated=result.updated,
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
        rows_read=len(entities_rows),
        valid_rows=len(valid_rows),
        warnings_count=len(warnings),
        result=result,
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
