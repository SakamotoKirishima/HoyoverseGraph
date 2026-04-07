"""CLI ingestion step for claims_seed -> PostgreSQL claims.

Usage:
    python -m ingestion.ingest_claims --workbook path/to/file.xlsx
    python -m ingestion.ingest_claims --workbook path/to/file.xlsx --dry-run

Flow:
1. Read workbook sheets needed for claims validation
2. Validate claims via existing validators
3. Optionally perform DB existence safety checks for FK targets
4. Write claims in two phases (single transaction):
   - phase 1: upsert claims with self-references set to NULL
   - phase 2: update supersedes/contradicts references
"""

from __future__ import annotations

import argparse
import logging
import os
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

from dotenv import load_dotenv

from ingestion.db import (
    UpsertSummary,
    fetch_existing_ids,
    get_connection,
    update_claim_relationship_refs,
    upsert_claims_phase1,
)
from ingestion.excel_reader import read_claims_workbook
from ingestion.logging_utils import configure_logging, generate_run_id, log_kv
from ingestion.validators import validate_claims_rows

CONFIDENCE_TO_NUMERIC: dict[str, Decimal] = {
    "high": Decimal("0.900"),
    "medium": Decimal("0.600"),
    "low": Decimal("0.300"),
}


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for claims ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest claims_seed from workbook into PostgreSQL."
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
        help="Read + validate + summarize only, skip DB writes.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging level.",
    )
    return parser.parse_args()


def _empty_to_none(value: Any) -> Any:
    """Convert blank string values to None."""
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _normalize_confidence(value: Any) -> Decimal | None:
    """Map confidence enum string to numeric DB value."""
    value = _empty_to_none(value)
    if value is None:
        return None
    if isinstance(value, str):
        return CONFIDENCE_TO_NUMERIC.get(value.strip().lower())
    return None


def normalize_claim_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Normalize validated claim rows before DB writes.

    Normalization:
    - empty strings -> None
    - confidence high/medium/low -> numeric Decimal
    """
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        row_copy = {k: _empty_to_none(v) for k, v in dict(row).items()}
        row_copy["confidence"] = _normalize_confidence(row_copy.get("confidence"))
        normalized_rows.append(row_copy)
    return normalized_rows


def print_messages(title: str, messages: list[str]) -> None:
    """Print a labelled list of validation/safety messages."""
    if not messages:
        return
    print(title)
    for message in messages:
        print(f"- {message}")


def print_summary(
    *,
    claim_rows_read: int,
    valid_claim_rows: int,
    claim_warnings: int,
    result: UpsertSummary,
    supersedes_count: int,
    contradicts_count: int,
    dry_run: bool,
) -> None:
    """Print final claims ingestion summary."""
    print(
        "Summary: "
        f"claim_rows_read={claim_rows_read} "
        f"valid_claim_rows={valid_claim_rows} "
        f"claim_warnings={claim_warnings} "
        f"inserted={result.inserted} "
        f"updated={result.updated} "
        f"supersedes_count={supersedes_count} "
        f"contradicts_count={contradicts_count} "
        f"dry_run={dry_run}"
    )


def _collect_fk_ids(
    rows: list[Mapping[str, Any]],
) -> tuple[set[str], set[str], set[str]]:
    """Collect FK target IDs from normalized claim rows."""
    entity_ids: set[str] = set()
    source_ids: set[str] = set()
    asset_ids: set[str] = set()

    for row in rows:
        subject_id = row.get("subject_entity_id")
        object_id = row.get("object_entity_id")
        source_id = row.get("source_id")
        asset_id = row.get("asset_id")

        if isinstance(subject_id, str):
            entity_ids.add(subject_id)
        if isinstance(object_id, str):
            entity_ids.add(object_id)
        if isinstance(source_id, str):
            source_ids.add(source_id)
        if isinstance(asset_id, str):
            asset_ids.add(asset_id)

    return entity_ids, source_ids, asset_ids


def _db_fk_safety_errors(conn: Any, rows: list[Mapping[str, Any]]) -> list[str]:
    """Run DB-side FK existence checks for claims ingestion safety."""
    errors: list[str] = []
    entity_ids, source_ids, asset_ids = _collect_fk_ids(rows)

    existing_entities = fetch_existing_ids(
        conn, table_name="entities", id_column="entity_id", ids=entity_ids
    )
    existing_sources = fetch_existing_ids(
        conn, table_name="sources", id_column="source_id", ids=source_ids
    )
    existing_assets = fetch_existing_ids(
        conn, table_name="source_assets", id_column="asset_id", ids=asset_ids
    )

    missing_entities = sorted(entity_ids - existing_entities)
    missing_sources = sorted(source_ids - existing_sources)
    missing_assets = sorted(asset_ids - existing_assets)

    if missing_entities:
        errors.append(
            "Missing referenced entities in DB: "
            + ", ".join(missing_entities)
            + ". Run entity ingestion first."
        )
    if missing_sources:
        errors.append(
            "Missing referenced sources in DB: "
            + ", ".join(missing_sources)
            + ". Run sources ingestion first."
        )
    if missing_assets:
        errors.append(
            "Missing referenced source_assets in DB: "
            + ", ".join(missing_assets)
            + ". Run source_assets ingestion first."
        )

    return errors


def main() -> int:
    """Run claims ingestion pipeline.

    Exit codes:
    - 0: success
    - 1: validation/safety failure
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
        script="ingest_claims",
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
            sheets="claims_seed,entities_seed,relationship_types,sources_registry,source_assets",
        )
        (
            claims_rows,
            entities_rows,
            relationship_types_rows,
            sources_rows,
            source_assets_rows,
        ) = read_claims_workbook(args.workbook)
        log_kv(
            logger,
            logging.INFO,
            "workbook_load_complete",
            run_id=run_id,
            claims_rows=len(claims_rows),
            entities_rows=len(entities_rows),
            relationship_types_rows=len(relationship_types_rows),
            sources_rows=len(sources_rows),
            source_assets_rows=len(source_assets_rows),
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
    log_kv(logger, logging.INFO, "validation_start", run_id=run_id, sheet="claims_seed")
    valid_claim_rows, claim_errors, claim_warnings = validate_claims_rows(
        claims_rows=claims_rows,
        entities_rows=entities_rows,
        relationship_types_rows=relationship_types_rows,
        sources_rows=sources_rows,
        source_assets_rows=source_assets_rows,
    )
    validation_duration = perf_counter() - validation_start
    log_kv(
        logger,
        logging.INFO,
        "validation_complete",
        run_id=run_id,
        valid_rows=len(valid_claim_rows),
        errors=len(claim_errors),
        warnings=len(claim_warnings),
        duration_seconds=f"{validation_duration:.3f}",
    )

    if claim_errors:
        for message in claim_errors:
            log_kv(logger, logging.ERROR, "validation_error", run_id=run_id, message=message)
        for message in claim_warnings:
            log_kv(
                logger,
                logging.WARNING,
                "validation_warning",
                run_id=run_id,
                message=message,
            )
        print_messages("Claim validation errors:", claim_errors)
        print_messages("Claim validation warnings:", claim_warnings)
        print_summary(
            claim_rows_read=len(claims_rows),
            valid_claim_rows=len(valid_claim_rows),
            claim_warnings=len(claim_warnings),
            result=UpsertSummary(inserted=0, updated=0),
            supersedes_count=0,
            contradicts_count=0,
            dry_run=args.dry_run,
        )
        return 1

    for message in claim_warnings:
        log_kv(
            logger,
            logging.WARNING,
            "validation_warning",
            run_id=run_id,
            message=message,
        )
    print_messages("Claim validation warnings:", claim_warnings)
    normalized_claim_rows = normalize_claim_rows(valid_claim_rows)
    log_kv(
        logger,
        logging.INFO,
        "normalization_complete",
        run_id=run_id,
        normalized_rows=len(normalized_claim_rows),
    )

    supersedes_count = sum(
        1 for row in normalized_claim_rows if row.get("supersedes_claim_id") is not None
    )
    contradicts_count = sum(
        1 for row in normalized_claim_rows if row.get("contradicts_claim_id") is not None
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
            claim_rows_read=len(claims_rows),
            valid_claim_rows=len(valid_claim_rows),
            claim_warnings=len(claim_warnings),
            result=UpsertSummary(inserted=0, updated=0),
            supersedes_count=supersedes_count,
            contradicts_count=contradicts_count,
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
            log_kv(logger, logging.INFO, "db_fk_safety_check_start", run_id=run_id)
            safety_errors = _db_fk_safety_errors(conn, normalized_claim_rows)
            log_kv(
                logger,
                logging.INFO,
                "db_fk_safety_check_complete",
                run_id=run_id,
                errors=len(safety_errors),
            )
            if safety_errors:
                for message in safety_errors:
                    log_kv(
                        logger,
                        logging.ERROR,
                        "db_fk_safety_error",
                        run_id=run_id,
                        message=message,
                    )
                print_messages("DB foreign-key safety check errors:", safety_errors)
                print_summary(
                    claim_rows_read=len(claims_rows),
                    valid_claim_rows=len(valid_claim_rows),
                    claim_warnings=len(claim_warnings),
                    result=UpsertSummary(inserted=0, updated=0),
                    supersedes_count=supersedes_count,
                    contradicts_count=contradicts_count,
                    dry_run=False,
                )
                return 1

            log_kv(logger, logging.INFO, "transaction_start", run_id=run_id)
            with conn.transaction():
                log_kv(
                    logger,
                    logging.INFO,
                    "upsert_phase_start",
                    run_id=run_id,
                    phase="claims_phase1",
                )
                result = upsert_claims_phase1(conn, normalized_claim_rows)
                log_kv(
                    logger,
                    logging.INFO,
                    "upsert_phase_complete",
                    run_id=run_id,
                    phase="claims_phase1",
                    inserted=result.inserted,
                    updated=result.updated,
                )
                log_kv(
                    logger,
                    logging.INFO,
                    "upsert_phase_start",
                    run_id=run_id,
                    phase="claims_phase2",
                )
                update_claim_relationship_refs(conn, normalized_claim_rows)
                log_kv(
                    logger,
                    logging.INFO,
                    "upsert_phase_complete",
                    run_id=run_id,
                    phase="claims_phase2",
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
        print(f"Database error during claims ingestion: {exc}")
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
        claim_rows_read=len(claims_rows),
        valid_claim_rows=len(valid_claim_rows),
        claim_warnings=len(claim_warnings),
        result=result,
        supersedes_count=supersedes_count,
        contradicts_count=contradicts_count,
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
