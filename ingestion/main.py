"""CLI entrypoint for ontology workbook parsing.

This module loads a workbook via ``ingestion.reader`` and prints a short
per-sheet row-count summary.

Run:
    python -m ingestion.main <path-to-workbook.xlsx-or-xlsm>
Example:
    python -m ingestion.main docs/hoyoverse_ontology_v1.xlsm
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ingestion.reader import SHEETS_TO_PARSE, read_ontology_workbook


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for workbook ingestion."""
    parser = argparse.ArgumentParser(
        description="Read ontology workbook and print parsed row counts per sheet."
    )
    parser.add_argument(
        "workbook_path",
        type=Path,
        help="Path to ontology workbook (.xlsx/.xlsm).",
    )
    return parser.parse_args()


def main() -> int:
    """Run workbook reader and print per-sheet row summary."""
    args = parse_args()
    parsed = read_ontology_workbook(args.workbook_path)

    print("Parsed row counts by sheet:")
    for sheet_name in SHEETS_TO_PARSE:
        if sheet_name not in parsed:
            continue
        print(f"- {sheet_name}: {len(parsed[sheet_name])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
