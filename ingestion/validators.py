"""Validation helpers for entities_seed and claims_seed ingestion data.

This module validates parsed workbook rows (required fields, formats, allowed
values, and duplicates) and returns ``valid_rows``, ``errors``, and
``warnings`` for downstream pipeline steps.

Run (quick import check):
    python -c "from ingestion.validators import validate_entities_rows, validate_claims_rows; print('ok')"
Typical usage (Python):
    from ingestion.validators import validate_entities_rows, validate_claims_rows
    valid_entity_rows, entity_errors, entity_warnings = validate_entities_rows(entities_rows, entity_type_rows)
    valid_claim_rows, claim_errors, claim_warnings = validate_claims_rows(
        claims_rows, entities_rows, relationship_types_rows, sources_rows, source_assets_rows
    )
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

ENTITY_ID_PATTERN = re.compile(r"^ENT-\d{4}$")
REQUIRED_ENTITY_FIELDS: tuple[str, ...] = ("entity_id", "canonical_name", "entity_type")
ALLOWED_STARTER_STATUS: set[str] = {"seed", "candidate", "backlog"}
CLAIM_ID_PATTERN = re.compile(r"^CLM-\d{4}$")
REQUIRED_CLAIM_FIELDS: tuple[str, ...] = (
    "claim_id",
    "subject_entity_id",
    "predicate",
    "object_entity_id",
    "source_id",
)
ALLOWED_CONFIDENCE_VALUES: set[str] = {"high", "medium", "low"}


def _normalize_row_values(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of row with trimmed strings and empty strings converted to None."""
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, str):
            stripped = value.strip()
            normalized[key] = stripped if stripped != "" else None
        else:
            normalized[key] = value
    return normalized


def _extract_allowed_entity_types(entity_type_rows: Sequence[Mapping[str, Any]]) -> set[str]:
    """Extract allowed entity types from entity_types rows."""
    allowed: set[str] = set()
    for row in entity_type_rows:
        value = row.get("entity_type_code")
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed:
                allowed.add(trimmed)
    return allowed


def _extract_non_empty_str_values(
    rows: Sequence[Mapping[str, Any]],
    key: str,
) -> set[str]:
    """Extract trimmed non-empty string values from a specific column key."""
    values: set[str] = set()
    for row in rows:
        value = row.get(key)
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed:
                values.add(trimmed)
    return values


def validate_entity_row(
    row: Mapping[str, Any],
    row_number: int,
    allowed_entity_types: set[str],
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Validate one entities_seed row.

    Args:
        row: Parsed entity row keyed by original column names.
        row_number: Workbook row number for error reporting.
        allowed_entity_types: Valid entity_type values from entity_types sheet.

    Returns:
        A tuple of (normalized_row, errors, warnings).
    """
    normalized = _normalize_row_values(row)
    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_ENTITY_FIELDS:
        if normalized.get(field) is None:
            errors.append(f"Row {row_number}: missing required field '{field}'.")

    entity_id = normalized.get("entity_id")
    if entity_id is not None and (not isinstance(entity_id, str) or not ENTITY_ID_PATTERN.match(entity_id)):
        errors.append(f"Row {row_number}: entity_id '{entity_id}' must match ENT-####.")

    entity_type = normalized.get("entity_type")
    if isinstance(entity_type, str) and entity_type not in allowed_entity_types:
        errors.append(
            f"Row {row_number}: entity_type '{entity_type}' is not in entity_types."
        )

    starter_status = normalized.get("starter_status")
    if starter_status is not None:
        if not isinstance(starter_status, str) or starter_status not in ALLOWED_STARTER_STATUS:
            errors.append(
                f"Row {row_number}: starter_status '{starter_status}' must be one of "
                f"{sorted(ALLOWED_STARTER_STATUS)}."
            )

    return normalized, errors, warnings


def validate_entities_rows(
    entities_rows: Sequence[Mapping[str, Any]],
    entity_type_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Validate entities_seed rows and return valid rows, errors, and warnings."""
    allowed_entity_types = _extract_allowed_entity_types(entity_type_rows)
    errors: list[str] = []
    warnings: list[str] = []
    valid_candidates: list[tuple[int, dict[str, Any]]] = []

    if not allowed_entity_types:
        warnings.append(
            "No entity_type_code values found in entity_types; entity_type checks may fail."
        )

    for idx, row in enumerate(entities_rows, start=2):
        normalized, row_errors, row_warnings = validate_entity_row(
            row=row,
            row_number=idx,
            allowed_entity_types=allowed_entity_types,
        )
        errors.extend(row_errors)
        warnings.extend(row_warnings)
        if not row_errors:
            valid_candidates.append((idx, normalized))

    id_to_rows: dict[str, list[int]] = {}
    combo_to_rows: dict[tuple[str, str], list[int]] = {}

    for row_number, row in valid_candidates:
        entity_id = row.get("entity_id")
        canonical_name = row.get("canonical_name")
        entity_type = row.get("entity_type")

        if isinstance(entity_id, str):
            id_to_rows.setdefault(entity_id, []).append(row_number)
        if isinstance(canonical_name, str) and isinstance(entity_type, str):
            combo_to_rows.setdefault((canonical_name, entity_type), []).append(row_number)

    duplicate_rows: set[int] = set()
    for entity_id, row_numbers in id_to_rows.items():
        if len(row_numbers) > 1:
            duplicate_rows.update(row_numbers)
            errors.append(
                f"Duplicate entity_id '{entity_id}' found at rows {sorted(row_numbers)}."
            )

    for (canonical_name, entity_type), row_numbers in combo_to_rows.items():
        if len(row_numbers) > 1:
            duplicate_rows.update(row_numbers)
            errors.append(
                "Duplicate (canonical_name, entity_type) "
                f"('{canonical_name}', '{entity_type}') found at rows {sorted(row_numbers)}."
            )

    valid_rows = [
        row for row_number, row in valid_candidates if row_number not in duplicate_rows
    ]

    return valid_rows, errors, warnings


def validate_claim_row(
    row: Mapping[str, Any],
    row_number: int,
    valid_entity_ids: set[str],
    valid_predicates: set[str],
    valid_source_ids: set[str],
    valid_asset_ids: set[str],
    valid_claim_ids: set[str],
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Validate one claims_seed row.

    Args:
        row: Parsed claim row keyed by original column names.
        row_number: Workbook row number for error reporting.
        valid_entity_ids: Existing entity IDs from entities_seed.
        valid_predicates: Allowed predicate codes from relationship_types.
        valid_source_ids: Existing source IDs from sources_registry.
        valid_asset_ids: Existing asset IDs from source_assets.
        valid_claim_ids: Valid claim IDs from claims_seed for self references.

    Returns:
        A tuple of (normalized_row, errors, warnings).
    """
    normalized = _normalize_row_values(row)
    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_CLAIM_FIELDS:
        if normalized.get(field) is None:
            errors.append(f"Row {row_number}: missing required field '{field}'.")

    claim_id = normalized.get("claim_id")
    if claim_id is not None and (not isinstance(claim_id, str) or not CLAIM_ID_PATTERN.match(claim_id)):
        errors.append(f"Row {row_number}: claim_id '{claim_id}' must match CLM-####.")

    subject_entity_id = normalized.get("subject_entity_id")
    if isinstance(subject_entity_id, str) and subject_entity_id not in valid_entity_ids:
        errors.append(
            f"Row {row_number}: subject_entity_id '{subject_entity_id}' does not exist in entities_seed."
        )

    object_entity_id = normalized.get("object_entity_id")
    if isinstance(object_entity_id, str) and object_entity_id not in valid_entity_ids:
        errors.append(
            f"Row {row_number}: object_entity_id '{object_entity_id}' does not exist in entities_seed."
        )

    source_id = normalized.get("source_id")
    if isinstance(source_id, str) and source_id not in valid_source_ids:
        errors.append(f"Row {row_number}: source_id '{source_id}' does not exist in sources_registry.")

    asset_id = normalized.get("asset_id")
    if asset_id is not None:
        if not isinstance(asset_id, str) or asset_id not in valid_asset_ids:
            errors.append(
                f"Row {row_number}: asset_id '{asset_id}' does not exist in source_assets."
            )

    predicate = normalized.get("predicate")
    if isinstance(predicate, str) and predicate not in valid_predicates:
        errors.append(
            f"Row {row_number}: predicate '{predicate}' is not in relationship_types."
        )

    confidence = normalized.get("confidence")
    if confidence is not None:
        if not isinstance(confidence, str) or confidence not in ALLOWED_CONFIDENCE_VALUES:
            errors.append(
                f"Row {row_number}: confidence '{confidence}' must be one of "
                f"{sorted(ALLOWED_CONFIDENCE_VALUES)}."
            )

    supersedes_claim_id = normalized.get("supersedes_claim_id")
    if supersedes_claim_id is not None:
        if not isinstance(supersedes_claim_id, str) or supersedes_claim_id not in valid_claim_ids:
            errors.append(
                f"Row {row_number}: supersedes_claim_id '{supersedes_claim_id}' must reference a valid claim_id."
            )
        elif isinstance(claim_id, str) and supersedes_claim_id == claim_id:
            errors.append(f"Row {row_number}: a claim cannot supersede itself ('{claim_id}').")

    contradicts_claim_id = normalized.get("contradicts_claim_id")
    if contradicts_claim_id is not None:
        if not isinstance(contradicts_claim_id, str) or contradicts_claim_id not in valid_claim_ids:
            errors.append(
                f"Row {row_number}: contradicts_claim_id '{contradicts_claim_id}' must reference a valid claim_id."
            )
        elif isinstance(claim_id, str) and contradicts_claim_id == claim_id:
            errors.append(f"Row {row_number}: a claim cannot contradict itself ('{claim_id}').")

    return normalized, errors, warnings


def validate_claims_rows(
    claims_rows: Sequence[Mapping[str, Any]],
    entities_rows: Sequence[Mapping[str, Any]],
    relationship_types_rows: Sequence[Mapping[str, Any]],
    sources_rows: Sequence[Mapping[str, Any]],
    source_assets_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Validate claims_seed rows and return valid rows, errors, and warnings."""
    valid_entity_ids = _extract_non_empty_str_values(entities_rows, "entity_id")
    valid_predicates = _extract_non_empty_str_values(
        relationship_types_rows, "relationship_type_code"
    )
    valid_source_ids = _extract_non_empty_str_values(sources_rows, "source_id")
    valid_asset_ids = _extract_non_empty_str_values(source_assets_rows, "asset_id")

    normalized_claim_rows = [_normalize_row_values(row) for row in claims_rows]
    valid_claim_ids = {
        claim_id
        for claim_id in (
            row.get("claim_id") for row in normalized_claim_rows
        )
        if isinstance(claim_id, str) and CLAIM_ID_PATTERN.match(claim_id)
    }

    errors: list[str] = []
    warnings: list[str] = []
    valid_candidates: list[tuple[int, dict[str, Any]]] = []

    for idx, normalized_row in enumerate(normalized_claim_rows, start=2):
        normalized, row_errors, row_warnings = validate_claim_row(
            row=normalized_row,
            row_number=idx,
            valid_entity_ids=valid_entity_ids,
            valid_predicates=valid_predicates,
            valid_source_ids=valid_source_ids,
            valid_asset_ids=valid_asset_ids,
            valid_claim_ids=valid_claim_ids,
        )
        errors.extend(row_errors)
        warnings.extend(row_warnings)
        if not row_errors:
            valid_candidates.append((idx, normalized))

    claim_key_to_rows: dict[tuple[str, str, str, str], list[int]] = {}
    for row_number, row in valid_candidates:
        subject_entity_id = row.get("subject_entity_id")
        predicate = row.get("predicate")
        object_entity_id = row.get("object_entity_id")
        source_id = row.get("source_id")

        if (
            isinstance(subject_entity_id, str)
            and isinstance(predicate, str)
            and isinstance(object_entity_id, str)
            and isinstance(source_id, str)
        ):
            claim_key = (subject_entity_id, predicate, object_entity_id, source_id)
            claim_key_to_rows.setdefault(claim_key, []).append(row_number)

    duplicate_rows: set[int] = set()
    for claim_key, row_numbers in claim_key_to_rows.items():
        if len(row_numbers) > 1:
            duplicate_rows.update(row_numbers)
            errors.append(
                "Duplicate claim (subject_entity_id, predicate, object_entity_id, source_id) "
                f"{claim_key} found at rows {sorted(row_numbers)}."
            )

    valid_rows = [
        row for row_number, row in valid_candidates if row_number not in duplicate_rows
    ]

    return valid_rows, errors, warnings
