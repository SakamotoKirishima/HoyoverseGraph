"""Smoke test for source validation output using the ontology workbook."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ingestion.reader import read_ontology_workbook
from ingestion.validators import validate_sources_rows


def test_validate_sources_registry_prints_summary() -> None:
    """Load sources_registry, run validation, and print a concise summary."""
    workbook_path = REPO_ROOT / "docs" / "hoyoverse_ontology_v1.xlsm"

    parsed = read_ontology_workbook(workbook_path)
    valid_rows, errors, warnings = validate_sources_rows(parsed["sources_registry"])

    print("Validator output for sources_registry")
    print(f"total_rows={len(parsed['sources_registry'])}")
    print(f"valid_rows={len(valid_rows)}")
    print(f"errors={len(errors)}")
    print(f"warnings={len(warnings)}")

    if errors:
        print("All errors:")
        for error in errors:
            print(f"- {error}")
    if warnings:
        print("All warnings:")
        for warning in warnings:
            print(f"- {warning}")

    assert len(parsed["sources_registry"]) > 0
    assert len(valid_rows) <= len(parsed["sources_registry"])


if __name__ == "__main__":
    test_validate_sources_registry_prints_summary()
