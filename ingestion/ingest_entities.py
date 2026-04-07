"""CLI ingestion step for entities_seed -> PostgreSQL entities."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Mapping

from dotenv import load_dotenv

from ingestion.db import UpsertSummary, get_connection, upsert_entities
from ingestion.excel_reader import read_entities_workbook
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
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")

    try:
        entities_rows, entity_type_rows = read_entities_workbook(args.workbook)
    except Exception as exc:
        print(f"Error reading workbook: {exc}")
        return 2

    valid_rows, errors, warnings = validate_entities_rows(entities_rows, entity_type_rows)

    if errors:
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
        print_messages("Validation warnings:", warnings)

    normalized_rows = normalize_entity_rows(valid_rows)

    if args.dry_run:
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
        print("Error: DATABASE_URL environment variable is not set.")
        return 2

    try:
        with get_connection(database_url) as conn:
            result = upsert_entities(conn, normalized_rows)
    except Exception as exc:
        print(f"Database error during upsert: {exc}")
        return 2

    print_summary(
        rows_read=len(entities_rows),
        valid_rows=len(valid_rows),
        warnings_count=len(warnings),
        result=result,
        dry_run=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
