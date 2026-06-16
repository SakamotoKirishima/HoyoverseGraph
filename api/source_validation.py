"""Shared validation helpers for source_type and source_format.

This module centralizes canonical allowed values and normalization/validation
for source type/format so source create/update flows stay consistent.
"""

from __future__ import annotations

SOURCE_TYPE_ALLOWED: tuple[str, ...] = (
    "official_story",
    "official_databank",
    "official_profile",
    "official_companion",
    "community_wiki",
    "community_reference",
    "datamine",
    "internal_editorial",
    "other",
)

SOURCE_FORMAT_ALLOWED: tuple[str, ...] = (
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
)

WEB_LIKE_SOURCE_FORMATS: set[str] = {
    "official_page",
    "wiki",
    "social_post",
    "article",
    "patch_notes",
    "interview",
    "video",
    "trailer",
}


def _trim_or_none(value: str | None) -> str | None:
    """Trim whitespace and convert empty strings to None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def normalize_source_type(value: str | None) -> str | None:
    """Normalize source_type input."""
    return _trim_or_none(value)


def normalize_source_format(value: str | None) -> str | None:
    """Normalize source_format input."""
    return _trim_or_none(value)


def validate_source_type(value: str | None, *, required: bool) -> list[str]:
    """Validate source_type against allowed canonical codes."""
    if value is None:
        return ["source_type is required."] if required else []

    if value not in SOURCE_TYPE_ALLOWED:
        allowed = ", ".join(SOURCE_TYPE_ALLOWED)
        return [f"Invalid source_type '{value}'. Must be one of: {allowed}."]
    return []


def validate_source_format(value: str | None, *, required: bool) -> list[str]:
    """Validate source_format against allowed canonical codes."""
    if value is None:
        return ["source_format is required."] if required else []

    if value not in SOURCE_FORMAT_ALLOWED:
        allowed = ", ".join(SOURCE_FORMAT_ALLOWED)
        return [f"Invalid source_format '{value}'. Must be one of: {allowed}."]
    return []


def is_web_like_source_format(source_format: str | None) -> bool:
    """Return True when source_format requires URL by policy."""
    return isinstance(source_format, str) and source_format in WEB_LIKE_SOURCE_FORMATS
