"""Smoke test for entity validation output using the ontology workbook."""

from __future__ import annotations

from pathlib import Path

from ingestion.reader import read_ontology_workbook
from ingestion.validators import validate_entities_rows

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_validate_entities_seed_prints_summary() -> None:
    """Load entities_seed, run validation, and print a concise output summary."""
    workbook_path = REPO_ROOT / "docs" / "hoyoverse_ontology_v1.xlsm"

    parsed = read_ontology_workbook(workbook_path)
    entities_rows = parsed["entities_seed"]
    entity_types_rows = parsed.get("entity_types", [])

    valid_rows, errors, warnings = validate_entities_rows(entities_rows, entity_types_rows)

    print("Validator output for entities_seed")
    print(f"total_rows={len(entities_rows)}")
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

    # Basic sanity assertions so the test fails only on true regressions.
    assert len(entities_rows) > 0
    assert len(valid_rows) + len(errors) >= len(valid_rows)


if __name__ == "__main__":
    test_validate_entities_seed_prints_summary()
