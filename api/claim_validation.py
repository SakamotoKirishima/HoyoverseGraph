"""Shared predicate validation for Claims API create/update flows.

This module centralizes relationship_types-backed predicate checks so claim
endpoints enforce predicate usage consistently and can be extended later with
subject/object type compatibility rules.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


class PredicateCatalogUnavailableError(RuntimeError):
    """Raised when relationship_types rules cannot be loaded for validation."""


@lru_cache(maxsize=1)
def get_allowed_predicates() -> set[str]:
    """Load allowed predicate codes from ontology relationship_types.

    Raises:
        PredicateCatalogUnavailableError: When the ontology file or expected
            relationship_type_code values cannot be loaded.
    """
    try:
        from ingestion.reader import read_ontology_workbook

        repo_root = Path(__file__).resolve().parents[1]
        workbook_path = repo_root / "docs" / "hoyoverse_ontology_v1.xlsm"
        parsed = read_ontology_workbook(workbook_path)
    except Exception as exc:  # pragma: no cover - environment/config failure path
        raise PredicateCatalogUnavailableError(
            "Unable to load relationship_types from ontology workbook."
        ) from exc

    relationship_rows = parsed.get("relationship_types", [])
    allowed: set[str] = set()
    for row in relationship_rows:
        value = row.get("relationship_type_code")
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                allowed.add(stripped)

    if not allowed:
        raise PredicateCatalogUnavailableError(
            "No relationship_type_code values found in relationship_types."
        )
    return allowed


def validate_predicate_usage(
    predicate: str | None,
    *,
    subject_entity_type: str | None = None,
    object_entity_type: str | None = None,
) -> list[str]:
    """Validate predicate value against relationship_types.

    The optional entity-type arguments are reserved for future ontology rules
    where predicate applicability can be constrained by subject/object types.
    """
    _ = (subject_entity_type, object_entity_type)
    if predicate is None:
        return ["predicate is required."]

    allowed_predicates = get_allowed_predicates()
    if predicate not in allowed_predicates:
        return [f"predicate '{predicate}' is not in relationship_types."]
    return []
