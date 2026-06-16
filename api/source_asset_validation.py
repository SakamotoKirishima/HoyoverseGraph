"""Shared validation and normalization helpers for source asset CRUD flows."""

from __future__ import annotations

import re
from typing import Any, Mapping
from urllib.parse import urlparse

from api.source_validation import is_web_like_source_format

ASSET_ID_PATTERN = re.compile(r"^AST-(?:HI3|HSR|GI|GGZ|WIKI|HL|INT|GEN)-\d{4}$")
SOURCE_ID_PATTERN = re.compile(r"^SRC-(?:HI3|HSR|GI|GGZ|WIKI|HL|INT|GEN)-\d{4}$")

ASSET_TYPE_ALLOWED: set[str] = {
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
FILE_LIKE_ASSET_TYPES: set[str] = {"screenshot", "image", "document", "web_archive"}

GAME_LIKE_SOURCE_FORMATS: set[str] = {"game", "in_game_text"}

ALLOWED_ASSET_TYPES_FOR_GAME_LIKE: set[str] = {
    "screenshot",
    "image",
    "quote",
    "transcript_excerpt",
    "video_reference",
    "audio",
    "document",
    "other",
}
ALLOWED_ASSET_TYPES_FOR_MANGA: set[str] = {
    "image",
    "screenshot",
    "quote",
    "document",
    "transcript_excerpt",
    "other",
}
ALLOWED_ASSET_TYPES_FOR_INTERNAL_NOTE: set[str] = {"document", "quote", "other"}


def trim_or_none(value: str | None) -> str | None:
    """Trim whitespace and convert empty strings to None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def is_plausible_http_url(value: str) -> bool:
    """Return True for plausible HTTP/HTTPS URLs."""
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_asset_create_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize create payload fields."""
    return {
        "source_id": trim_or_none(payload.get("source_id")),
        "asset_type": trim_or_none(payload.get("asset_type")),
        "file_path_or_url": trim_or_none(payload.get("file_path_or_url")),
        "locator": trim_or_none(payload.get("locator")),
        "description": trim_or_none(payload.get("description")),
        "is_primary_evidence": (
            False
            if payload.get("is_primary_evidence") is None
            else payload.get("is_primary_evidence")
        ),
        "notes": trim_or_none(payload.get("notes")),
    }


def normalize_asset_patch_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize only explicitly provided patch payload fields."""
    normalized: dict[str, Any] = {}
    if "source_id" in payload:
        normalized["source_id"] = trim_or_none(payload.get("source_id"))
    if "asset_type" in payload:
        normalized["asset_type"] = trim_or_none(payload.get("asset_type"))
    if "file_path_or_url" in payload:
        normalized["file_path_or_url"] = trim_or_none(payload.get("file_path_or_url"))
    if "locator" in payload:
        normalized["locator"] = trim_or_none(payload.get("locator"))
    if "description" in payload:
        normalized["description"] = trim_or_none(payload.get("description"))
    if "is_primary_evidence" in payload:
        normalized["is_primary_evidence"] = payload.get("is_primary_evidence")
    if "notes" in payload:
        normalized["notes"] = trim_or_none(payload.get("notes"))
    return normalized


def merge_asset_patch(current: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    """Merge current row with normalized patch fields."""
    merged = {
        "source_id": current.get("source_id"),
        "asset_type": current.get("asset_type"),
        "file_path_or_url": current.get("file_path_or_url"),
        "locator": current.get("locator"),
        "description": current.get("description"),
        "is_primary_evidence": current.get("is_primary_evidence"),
        "notes": current.get("notes"),
    }
    merged.update(dict(patch))
    return merged


def derive_asset_domain_from_source_id(source_id: str) -> str | None:
    """Extract domain token from a valid source_id (SRC-{DOMAIN}-####)."""
    match = SOURCE_ID_PATTERN.match(source_id)
    if not match:
        return None
    parts = source_id.split("-")
    if len(parts) != 3:
        return None
    return parts[1]


def validate_asset_values(values: Mapping[str, Any]) -> list[str]:
    """Validate merged or create-normalized asset values."""
    errors: list[str] = []

    source_id = values.get("source_id")
    asset_type = values.get("asset_type")
    file_path_or_url = values.get("file_path_or_url")
    locator = values.get("locator")
    is_primary_evidence = values.get("is_primary_evidence")

    if not isinstance(source_id, str) or not SOURCE_ID_PATTERN.match(source_id):
        errors.append("source_id must match SRC-{DOMAIN}-####.")

    if not isinstance(asset_type, str):
        errors.append("asset_type is required.")
    elif asset_type not in ASSET_TYPE_ALLOWED:
        errors.append(f"asset_type '{asset_type}' is not allowed.")

    if file_path_or_url is None and locator is None:
        errors.append("At least one of file_path_or_url or locator must be provided.")

    if (
        isinstance(asset_type, str)
        and asset_type in TIMESTAMP_STYLE_ASSET_TYPES
        and locator is None
    ):
        errors.append(f"locator is required for asset_type '{asset_type}'.")

    if (
        isinstance(asset_type, str)
        and asset_type in FILE_LIKE_ASSET_TYPES
        and file_path_or_url is None
    ):
        errors.append(f"file_path_or_url is required for asset_type '{asset_type}'.")

    if isinstance(file_path_or_url, str):
        parsed = urlparse(file_path_or_url)
        # Validate URL only when value clearly looks like URL input.
        if (
            parsed.scheme
            or file_path_or_url.startswith("http://")
            or file_path_or_url.startswith("https://")
        ):
            if not is_plausible_http_url(file_path_or_url):
                errors.append("file_path_or_url must be a valid HTTP/HTTPS URL when URL-like.")

    if is_primary_evidence is not None and not isinstance(is_primary_evidence, bool):
        errors.append("is_primary_evidence must be a boolean or null.")

    return errors


def is_game_like_source_format(source_format: str | None) -> bool:
    """Return True when source_format is game-like."""
    return isinstance(source_format, str) and source_format in GAME_LIKE_SOURCE_FORMATS


def validate_source_asset_linkage(
    source_row: Mapping[str, Any],
    asset_values: Mapping[str, Any],
) -> list[str]:
    """Validate that source_asset payload is consistent with linked source record.

    This checks source_format-aware compatibility between asset representation
    and the source context, beyond bare FK existence.
    """
    errors: list[str] = []

    source_format = source_row.get("source_format")
    asset_type = asset_values.get("asset_type")
    file_path_or_url = asset_values.get("file_path_or_url")
    locator = asset_values.get("locator")

    if not isinstance(source_format, str) or not isinstance(asset_type, str):
        return errors

    if is_game_like_source_format(source_format):
        if asset_type not in ALLOWED_ASSET_TYPES_FOR_GAME_LIKE:
            errors.append(
                f"asset_type '{asset_type}' is not valid for source_format '{source_format}'."
            )
        if asset_type == "screenshot" and locator is None:
            errors.append(
                "locator is required for screenshot assets linked to game/in_game_text sources."
            )
        if asset_type == "web_archive":
            errors.append(
                f"asset_type 'web_archive' is not valid for source_format '{source_format}'."
            )

    elif is_web_like_source_format(source_format):
        if asset_type == "web_archive" and file_path_or_url is None:
            errors.append(
                "file_path_or_url is required for web_archive assets linked to web-like sources."
            )
        if (
            source_format in {"video", "trailer"}
            and asset_type == "video_reference"
            and locator is None
        ):
            errors.append(
                "locator is required for video_reference assets linked to video/trailer sources."
            )

    elif source_format == "manga":
        if asset_type not in ALLOWED_ASSET_TYPES_FOR_MANGA:
            errors.append(
                f"asset_type '{asset_type}' is not valid for source_format '{source_format}'."
            )

    elif source_format == "internal_note":
        if asset_type not in ALLOWED_ASSET_TYPES_FOR_INTERNAL_NOTE:
            errors.append(
                f"asset_type '{asset_type}' is not valid for source_format '{source_format}'."
            )

    return errors
