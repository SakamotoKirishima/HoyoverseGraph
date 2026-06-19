"""Shared entity validation and normalization rules for API create/update flows.

This module centralizes:
- canonical name / entity type checks
- starter status rules
- primary_scope_game alias normalization
- alias normalization + DB serialization
- ontology-backed entity_type hook (when available)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from ingestion.ingest_entities import PRIMARY_SCOPE_GAME_ALIASES

STARTER_STATUS_ALLOWED: set[str] = {"seed", "candidate", "backlog"}
PRIMARY_SCOPE_ALLOWED: set[str] = {
    "Honkai Impact 3",
    "Honkai: Star Rail",
    "Genshin Impact",
    "Gun Girls Z",
    "Multi",
}


def trim_to_none(value: str | None) -> str | None:
    """Trim string values and convert empty strings to None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def normalize_primary_scope_game(value: str | None) -> str | None:
    """Normalize primary_scope_game aliases to canonical values."""
    cleaned = trim_to_none(value)
    if cleaned is None:
        return None
    return PRIMARY_SCOPE_GAME_ALIASES.get(cleaned, cleaned)


def normalize_aliases(aliases: list[str] | None) -> list[str] | None:
    """Trim, drop-empty, and deduplicate aliases while preserving order."""
    if aliases is None:
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        stripped = alias.strip()
        if not stripped:
            continue
        key = stripped.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(stripped)

    return normalized if normalized else None


def serialize_aliases(aliases: list[str] | None) -> str | None:
    """Serialize alias list for DB storage."""
    normalized = normalize_aliases(aliases)
    if not normalized:
        return None
    return "|".join(normalized)


def deserialize_aliases(aliases_pipe_delimited: str | None) -> list[str]:
    """Deserialize DB alias string to API list form."""
    if aliases_pipe_delimited is None:
        return []
    parts = [piece.strip() for piece in aliases_pipe_delimited.split("|")]
    return [piece for piece in parts if piece]


@lru_cache(maxsize=1)
def get_allowed_entity_types() -> set[str]:
    """Load allowed entity types from ontology workbook if available.

    If loading fails, returns an empty set to preserve a lightweight validation hook.
    """
    try:
        from ingestion.reader import read_ontology_workbook
        from ingestion.validators import _extract_allowed_entity_types

        repo_root = Path(__file__).resolve().parents[1]
        workbook_path = repo_root / "docs" / "hoyoverse_ontology_v1.xlsm"
        parsed = read_ontology_workbook(workbook_path)
        entity_type_rows = parsed.get("entity_types", [])
        return _extract_allowed_entity_types(entity_type_rows)
    except Exception:
        return set()


def _validate_entity_values(values: Mapping[str, Any]) -> list[str]:
    """Validate fully-normalized entity values."""
    errors: list[str] = []

    canonical_name = values.get("canonical_name")
    entity_type = values.get("entity_type")
    primary_scope_game = values.get("primary_scope_game")
    starter_status = values.get("starter_status")

    if canonical_name is None:
        errors.append("canonical_name is required.")
    if entity_type is None:
        errors.append("entity_type is required.")

    if starter_status is not None and starter_status not in STARTER_STATUS_ALLOWED:
        errors.append("starter_status must be one of: seed, candidate, backlog.")

    if primary_scope_game is not None and primary_scope_game not in PRIMARY_SCOPE_ALLOWED:
        errors.append(
            "primary_scope_game must be one of: "
            "Honkai Impact 3, Honkai: Star Rail, Genshin Impact, Gun Girls Z, Multi."
        )

    allowed_entity_types = get_allowed_entity_types()
    # Ontology-backed hook: enforce only when ontology values are available.
    if entity_type is not None and allowed_entity_types and entity_type not in allowed_entity_types:
        errors.append(f"entity_type '{entity_type}' is not defined in ontology entity_types.")

    return errors


def validate_entity_payload_for_create(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Normalize and validate create payload values."""
    normalized = {
        "canonical_name": trim_to_none(payload.get("canonical_name")),
        "entity_type": trim_to_none(payload.get("entity_type")),
        "primary_scope_game": normalize_primary_scope_game(payload.get("primary_scope_game")),
        "display_label": trim_to_none(payload.get("display_label")),
        "aliases_pipe_delimited": serialize_aliases(payload.get("aliases")),
        "short_description": trim_to_none(payload.get("short_description")),
        "starter_status": trim_to_none(payload.get("starter_status")),
        "notes": trim_to_none(payload.get("notes")),
    }
    return normalized, _validate_entity_values(normalized)


def validate_entity_patch_payload(
    patch_payload: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Normalize PATCH payload while preserving omitted vs explicit null semantics."""
    normalized_patch: dict[str, Any] = {}
    errors: list[str] = []

    if "canonical_name" in patch_payload:
        normalized_patch["canonical_name"] = trim_to_none(patch_payload.get("canonical_name"))
        if normalized_patch["canonical_name"] is None:
            errors.append("canonical_name cannot be blank.")

    if "entity_type" in patch_payload:
        normalized_patch["entity_type"] = trim_to_none(patch_payload.get("entity_type"))
        if normalized_patch["entity_type"] is None:
            errors.append("entity_type cannot be blank.")

    if "primary_scope_game" in patch_payload:
        normalized_patch["primary_scope_game"] = normalize_primary_scope_game(
            patch_payload.get("primary_scope_game")
        )

    if "display_label" in patch_payload:
        normalized_patch["display_label"] = trim_to_none(patch_payload.get("display_label"))

    if "aliases" in patch_payload:
        aliases_value = patch_payload.get("aliases")
        if aliases_value is not None and not isinstance(aliases_value, list):
            errors.append("aliases must be a list of strings or null.")
        else:
            normalized_patch["aliases_pipe_delimited"] = serialize_aliases(aliases_value)

    if "short_description" in patch_payload:
        normalized_patch["short_description"] = trim_to_none(patch_payload.get("short_description"))

    if "starter_status" in patch_payload:
        normalized_patch["starter_status"] = trim_to_none(patch_payload.get("starter_status"))

    if "notes" in patch_payload:
        normalized_patch["notes"] = trim_to_none(patch_payload.get("notes"))

    return normalized_patch, errors


def merge_entity_patch(
    current_row: Mapping[str, Any],
    patch_values: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge DB entity row with normalized patch values."""
    merged = {
        "canonical_name": current_row.get("canonical_name"),
        "entity_type": current_row.get("entity_type"),
        "primary_scope_game": current_row.get("primary_scope_game"),
        "display_label": current_row.get("display_label"),
        "aliases_pipe_delimited": current_row.get("aliases_pipe_delimited"),
        "short_description": current_row.get("short_description"),
        "starter_status": current_row.get("starter_status"),
        "notes": current_row.get("notes"),
    }
    merged.update(dict(patch_values))
    return merged


def validate_merged_entity_values(values: Mapping[str, Any]) -> list[str]:
    """Validate merged entity values for update flows."""
    return _validate_entity_values(values)
