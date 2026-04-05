"""Validation helpers for workbook ingestion sheets.

This module validates parsed workbook rows (required fields, formats, allowed
values, and duplicates) and returns ``valid_rows``, ``errors``, and
``warnings`` for downstream pipeline steps.

Run (quick import check):
    python -c "from ingestion.validators import validate_entities_rows, validate_claims_rows, validate_sources_rows, validate_source_assets_rows; print('ok')"
Typical usage (Python):
    from ingestion.validators import (
        validate_entities_rows,
        validate_claims_rows,
        validate_sources_rows,
        validate_source_assets_rows,
    )
    valid_entity_rows, entity_errors, entity_warnings = validate_entities_rows(entities_rows, entity_type_rows)
    valid_claim_rows, claim_errors, claim_warnings = validate_claims_rows(
        claims_rows, entities_rows, relationship_types_rows, sources_rows, source_assets_rows
    )
    valid_source_rows, source_errors, source_warnings = validate_sources_rows(sources_rows)
    valid_asset_rows, asset_errors, asset_warnings = validate_source_assets_rows(
        source_asset_rows, sources_rows
    )
"""

from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

ENTITY_ID_PATTERN = re.compile(r"^ENT-\d{4}$")
REQUIRED_ENTITY_FIELDS: tuple[str, ...] = ("entity_id", "canonical_name", "entity_type")
ALLOWED_STARTER_STATUS: set[str] = {"seed", "candidate", "backlog"}
ALLOWED_GAME_VALUES: set[str] = {
    "Honkai Impact 3",
    "Honkai: Star Rail",
    "Genshin Impact",
    "Gun Girls Z",
    "Multi",
}
GAME_VALUE_ALIASES: dict[str, str] = {
    "HI3": "Honkai Impact 3",
    "Honkai Impact 3rd": "Honkai Impact 3",
    "HSR": "Honkai: Star Rail",
    "Genshin": "Genshin Impact",
    "GGZ": "Gun Girls Z",
    "Guns Girl Z": "Gun Girls Z",
    "Cross-title": "Multi",
}
CLAIM_ID_PATTERN = re.compile(r"^CLM-\d{4}$")
ID_DOMAINS: tuple[str, ...] = ("HI3", "HSR", "GI", "GGZ", "WIKI", "HL", "INT", "GEN")
_ID_DOMAIN_PATTERN = "(?:" + "|".join(ID_DOMAINS) + ")"
SOURCE_ID_PATTERN = re.compile(rf"^SRC-{_ID_DOMAIN_PATTERN}-\d{{4}}$")
ASSET_ID_PATTERN = re.compile(rf"^AST-{_ID_DOMAIN_PATTERN}-\d{{4}}$")
REQUIRED_CLAIM_FIELDS: tuple[str, ...] = (
    "claim_id",
    "subject_entity_id",
    "predicate",
    "object_entity_id",
    "source_id",
)
ALLOWED_CONFIDENCE_VALUES: set[str] = {"high", "medium", "low"}
REQUIRED_SOURCE_FIELDS: tuple[str, ...] = (
    "source_id",
    "title",
    "source_type",
    "source_format",
    "reliability_tier",
)
ALLOWED_SOURCE_TYPES: set[str] = {
    "official_story",
    "official_databank",
    "official_profile",
    "official_companion",
    "community_wiki",
    "community_reference",
    "datamine",
    "internal_editorial",
    "other",
}
ALLOWED_SOURCE_FORMATS: set[str] = {
    "game",
    "in_game_text",
    "manga",
    "article",
    "interview",
    "patch_notes",
    "trailer",
    "video",
    "official_page",
    "wiki",
    "social_post",
    "internal_note",
    "other",
}
ALLOWED_RELIABILITY_TIERS: set[str] = {"tier_1", "tier_2", "tier_3", "tier_4"}
ALLOWED_RELIABILITY_BY_SOURCE_TYPE: dict[str, set[str]] = {
    # Hard rules:
    # official_* -> tier_1 or tier_2
    # community_wiki -> NOT tier_1
    # community_reference -> tier_3 only
    # datamine -> tier_3 only
    # internal_editorial -> tier_4 only
    # other -> tier_3 or tier_4
    "official_story": {"tier_1", "tier_2"},
    "official_databank": {"tier_1", "tier_2"},
    "official_profile": {"tier_1", "tier_2"},
    "official_companion": {"tier_1", "tier_2"},
    "community_wiki": {"tier_2", "tier_3", "tier_4"},
    "community_reference": {"tier_3"},
    "datamine": {"tier_3"},
    "internal_editorial": {"tier_4"},
    "other": {"tier_3", "tier_4"},
}
WEB_SOURCE_FORMATS: set[str] = {
    "official_page",
    "wiki",
    "social_post",
    "article",
    "patch_notes",
    "interview",
    "video",
    "trailer",
}
REQUIRED_SOURCE_ASSET_FIELDS: tuple[str, ...] = ("asset_id", "source_id", "asset_type")
ALLOWED_SOURCE_ASSET_TYPES: set[str] = {
    "image",
    "screenshot",
    "document",
    "web_archive",
    "quote",
    "transcript_excerpt",
    "video_reference",
    "audio",
    "other",
}
TIMESTAMP_STYLE_ASSET_TYPES: set[str] = {"video_reference", "audio", "transcript_excerpt"}
FILE_EXPECTED_ASSET_TYPES: set[str] = {
    "screenshot",
    "image",
    "document",
    "web_archive",
}


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


def _is_plausible_url(value: str) -> bool:
    """Return True when value looks like a plausible HTTP/HTTPS URL."""
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_parseable_publication_date(value: Any) -> bool:
    """Return True when publication_date is a parseable date-like value."""
    if isinstance(value, (date, datetime)):
        return True
    if not isinstance(value, str):
        return False

    text = value.strip()
    if not text:
        return False

    date_formats = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y-%m",
        "%Y/%m",
        "%m/%d/%Y",
        "%Y",
    )
    for fmt in date_formats:
        try:
            datetime.strptime(text, fmt)
            return True
        except ValueError:
            continue
    return False


def _normalize_game_value(value: str) -> str:
    """Normalize game labels to canonical values for validation."""
    trimmed = value.strip()
    return GAME_VALUE_ALIASES.get(trimmed, trimmed)


def _normalize_bool_like(value: Any) -> Any:
    """Normalize common boolean-like values to bool, otherwise keep original."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "t", "yes", "y", "1"}:
            return True
        if text in {"false", "f", "no", "n", "0"}:
            return False
    return value


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

    primary_scope_game = normalized.get("primary_scope_game")
    if primary_scope_game is not None:
        if not isinstance(primary_scope_game, str):
            errors.append(
                f"Row {row_number}: primary_scope_game '{primary_scope_game}' must be a string."
            )
        else:
            canonical_game = _normalize_game_value(primary_scope_game)
            if canonical_game not in ALLOWED_GAME_VALUES:
                errors.append(
                    f"Row {row_number}: primary_scope_game '{primary_scope_game}' must be one of "
                    f"{sorted(ALLOWED_GAME_VALUES)}."
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


def validate_source_row(
    row: Mapping[str, Any],
    row_number: int,
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Validate one sources_registry row.

    Args:
        row: Parsed source row keyed by original column names.
        row_number: Workbook row number for error/warning reporting.

    Returns:
        A tuple of (normalized_row, errors, warnings).
    """
    normalized = _normalize_row_values(row)
    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_SOURCE_FIELDS:
        if normalized.get(field) is None:
            errors.append(f"Row {row_number}: missing required field '{field}'.")

    source_id = normalized.get("source_id")
    if source_id is not None and (
        not isinstance(source_id, str) or not SOURCE_ID_PATTERN.match(source_id)
    ):
        errors.append(
            f"Row {row_number}: source_id '{source_id}' must match "
            f"SRC-{{DOMAIN}}-#### where DOMAIN is one of {ID_DOMAINS}."
        )

    source_type = normalized.get("source_type")
    if source_type is not None:
        if not isinstance(source_type, str) or source_type not in ALLOWED_SOURCE_TYPES:
            errors.append(
                f"Row {row_number}: source_type '{source_type}' must be one of "
                f"{sorted(ALLOWED_SOURCE_TYPES)}."
            )

    source_format = normalized.get("source_format")
    if source_format is not None:
        if not isinstance(source_format, str) or source_format not in ALLOWED_SOURCE_FORMATS:
            errors.append(
                f"Row {row_number}: source_format '{source_format}' must be one of "
                f"{sorted(ALLOWED_SOURCE_FORMATS)}."
            )

    reliability_tier = normalized.get("reliability_tier")
    if reliability_tier is not None:
        if not isinstance(reliability_tier, str) or reliability_tier not in ALLOWED_RELIABILITY_TIERS:
            errors.append(
                f"Row {row_number}: reliability_tier '{reliability_tier}' must be one of "
                f"{sorted(ALLOWED_RELIABILITY_TIERS)}."
            )

    url = normalized.get("url")
    if url is not None:
        if not isinstance(url, str) or not _is_plausible_url(url):
            errors.append(f"Row {row_number}: url '{url}' is not a plausible HTTP/HTTPS URL.")
    elif isinstance(source_format, str) and source_format in WEB_SOURCE_FORMATS:
        warnings.append(
            f"Row {row_number}: missing url for web-like source_format '{source_format}'."
        )

    publication_date = normalized.get("publication_date")
    if publication_date is not None and not _is_parseable_publication_date(publication_date):
        errors.append(
            f"Row {row_number}: publication_date '{publication_date}' is not parseable."
        )

    game = normalized.get("game")
    if game is None:
        warnings.append(f"Row {row_number}: missing game.")
    elif not isinstance(game, str):
        errors.append(f"Row {row_number}: game '{game}' must be a string.")
    else:
        canonical_game = _normalize_game_value(game)
        if canonical_game not in ALLOWED_GAME_VALUES:
            errors.append(
                f"Row {row_number}: game '{game}' must be one of "
                f"{sorted(ALLOWED_GAME_VALUES)}."
            )
    if normalized.get("scope") is None:
        warnings.append(f"Row {row_number}: missing scope.")

    if isinstance(source_type, str) and isinstance(reliability_tier, str):
        allowed_tiers = ALLOWED_RELIABILITY_BY_SOURCE_TYPE.get(source_type)
        if allowed_tiers is not None and reliability_tier not in allowed_tiers:
            errors.append(
                f"Row {row_number}: reliability_tier '{reliability_tier}' is invalid for "
                f"source_type '{source_type}'. Allowed: {sorted(allowed_tiers)}."
            )

        # Optional warnings:
        if source_type == "official_story" and reliability_tier != "tier_1":
            warnings.append(
                f"Row {row_number}: source_type 'official_story' is strongest at tier_1 "
                f"(found '{reliability_tier}')."
            )
        if source_type == "official_databank" and reliability_tier != "tier_1":
            warnings.append(
                f"Row {row_number}: source_type 'official_databank' is strongest at tier_1 "
                f"(found '{reliability_tier}')."
            )
        if source_type == "community_wiki" and reliability_tier == "tier_3":
            warnings.append(
                f"Row {row_number}: source_type 'community_wiki' at tier_3 may be too low."
            )

    return normalized, errors, warnings


def validate_sources_rows(
    sources_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Validate sources_registry rows and return valid rows, errors, and warnings."""
    errors: list[str] = []
    warnings: list[str] = []
    valid_candidates: list[tuple[int, dict[str, Any]]] = []

    for idx, row in enumerate(sources_rows, start=2):
        normalized, row_errors, row_warnings = validate_source_row(
            row=row,
            row_number=idx,
        )
        errors.extend(row_errors)
        warnings.extend(row_warnings)
        if not row_errors:
            valid_candidates.append((idx, normalized))

    source_id_to_rows: dict[str, list[int]] = {}
    soft_duplicate_key_to_rows: dict[tuple[str, str, str | None, str | None], list[int]] = {}

    for row_number, row in valid_candidates:
        source_id = row.get("source_id")
        title = row.get("title")
        source_type = row.get("source_type")
        game = row.get("game")
        scope = row.get("scope")

        if isinstance(source_id, str):
            source_id_to_rows.setdefault(source_id, []).append(row_number)

        if isinstance(title, str) and isinstance(source_type, str):
            soft_key = (title, source_type, game if isinstance(game, str) else None, scope if isinstance(scope, str) else None)
            soft_duplicate_key_to_rows.setdefault(soft_key, []).append(row_number)

    duplicate_rows: set[int] = set()
    for source_id, row_numbers in source_id_to_rows.items():
        if len(row_numbers) > 1:
            duplicate_rows.update(row_numbers)
            errors.append(
                f"Duplicate source_id '{source_id}' found at rows {sorted(row_numbers)}."
            )

    for soft_key, row_numbers in soft_duplicate_key_to_rows.items():
        if len(row_numbers) > 1:
            warnings.append(
                "Likely duplicate source records (title, source_type, game, scope) "
                f"{soft_key} found at rows {sorted(row_numbers)}."
            )

    valid_rows = [
        row for row_number, row in valid_candidates if row_number not in duplicate_rows
    ]

    return valid_rows, errors, warnings


def validate_source_asset_row(
    row: Mapping[str, Any],
    row_number: int,
    valid_source_ids: set[str],
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Validate one source_assets row.

    Args:
        row: Parsed source_asset row keyed by original column names.
        row_number: Workbook row number for error/warning reporting.
        valid_source_ids: Existing source IDs from sources_registry.

    Returns:
        A tuple of (normalized_row, errors, warnings).
    """
    normalized = _normalize_row_values(row)
    normalized["is_primary_evidence"] = _normalize_bool_like(normalized.get("is_primary_evidence"))

    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_SOURCE_ASSET_FIELDS:
        if normalized.get(field) is None:
            errors.append(f"Row {row_number}: missing required field '{field}'.")

    asset_id = normalized.get("asset_id")
    if asset_id is not None and (
        not isinstance(asset_id, str) or not ASSET_ID_PATTERN.match(asset_id)
    ):
        errors.append(
            f"Row {row_number}: asset_id '{asset_id}' must match "
            f"AST-{{DOMAIN}}-#### where DOMAIN is one of {ID_DOMAINS}."
        )

    source_id = normalized.get("source_id")
    if isinstance(source_id, str) and source_id not in valid_source_ids:
        errors.append(
            f"Row {row_number}: source_id '{source_id}' does not exist in sources_registry."
        )

    asset_type = normalized.get("asset_type")
    if asset_type is not None:
        if not isinstance(asset_type, str) or asset_type not in ALLOWED_SOURCE_ASSET_TYPES:
            errors.append(
                f"Row {row_number}: asset_type '{asset_type}' must be one of "
                f"{sorted(ALLOWED_SOURCE_ASSET_TYPES)}."
            )

    file_path_or_url = normalized.get("file_path_or_url")
    locator = normalized.get("locator")
    if file_path_or_url is None and locator is None:
        errors.append(
            f"Row {row_number}: at least one of 'file_path_or_url' or 'locator' must be present."
        )

    is_primary_evidence = normalized.get("is_primary_evidence")
    if is_primary_evidence is not None and not isinstance(is_primary_evidence, bool):
        errors.append(
            f"Row {row_number}: is_primary_evidence '{is_primary_evidence}' must be boolean-like."
        )

    if normalized.get("description") is None:
        warnings.append(f"Row {row_number}: missing description.")

    if isinstance(asset_type, str) and asset_type in TIMESTAMP_STYLE_ASSET_TYPES and locator is None:
        warnings.append(
            f"Row {row_number}: missing locator for timestamp-style asset_type '{asset_type}'."
        )

    if isinstance(asset_type, str) and asset_type in FILE_EXPECTED_ASSET_TYPES:
        if not isinstance(file_path_or_url, str) or file_path_or_url.strip() == "":
            warnings.append(
                f"Row {row_number}: missing or suspicious file_path_or_url for asset_type '{asset_type}'."
            )

    return normalized, errors, warnings


def validate_source_assets_rows(
    source_asset_rows: Sequence[Mapping[str, Any]],
    sources_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Validate source_assets rows and return valid rows, errors, and warnings."""
    valid_source_ids = _extract_non_empty_str_values(sources_rows, "source_id")

    errors: list[str] = []
    warnings: list[str] = []
    valid_candidates: list[tuple[int, dict[str, Any]]] = []

    for idx, row in enumerate(source_asset_rows, start=2):
        normalized, row_errors, row_warnings = validate_source_asset_row(
            row=row,
            row_number=idx,
            valid_source_ids=valid_source_ids,
        )
        errors.extend(row_errors)
        warnings.extend(row_warnings)
        if not row_errors:
            valid_candidates.append((idx, normalized))

    duplicate_key_to_rows: dict[tuple[str, str, str | None, str | None], list[int]] = {}
    for row_number, row in valid_candidates:
        source_id = row.get("source_id")
        asset_type = row.get("asset_type")
        file_path_or_url = row.get("file_path_or_url")
        locator = row.get("locator")

        if isinstance(source_id, str) and isinstance(asset_type, str):
            key = (
                source_id,
                asset_type,
                file_path_or_url if isinstance(file_path_or_url, str) else None,
                locator if isinstance(locator, str) else None,
            )
            duplicate_key_to_rows.setdefault(key, []).append(row_number)

    duplicate_rows: set[int] = set()
    for key, row_numbers in duplicate_key_to_rows.items():
        if len(row_numbers) > 1:
            duplicate_rows.update(row_numbers)
            errors.append(
                "Duplicate source_asset (source_id, asset_type, file_path_or_url, locator) "
                f"{key} found at rows {sorted(row_numbers)}."
            )

    valid_rows = [
        row for row_number, row in valid_candidates if row_number not in duplicate_rows
    ]

    return valid_rows, errors, warnings
