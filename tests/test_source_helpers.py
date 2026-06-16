"""Unit tests for source validation and normalization helpers."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api import source_validation as sv
from api import sources
from api.entity_validation import normalize_primary_scope_game


def test_source_type_validation_valid() -> None:
    value = sv.normalize_source_type("official_story")
    assert sv.validate_source_type(value, required=True) == []


def test_source_type_validation_invalid() -> None:
    errors = sv.validate_source_type(sv.normalize_source_type("foo"), required=True)
    assert errors
    assert "Invalid source_type" in errors[0]


def test_source_type_validation_blank_fails() -> None:
    errors = sv.validate_source_type(sv.normalize_source_type("   "), required=True)
    assert errors == ["source_type is required."]


def test_source_format_validation_valid() -> None:
    value = sv.normalize_source_format("game")
    assert sv.validate_source_format(value, required=True) == []


def test_source_format_validation_invalid() -> None:
    errors = sv.validate_source_format(sv.normalize_source_format("foo"), required=True)
    assert errors
    assert "Invalid source_format" in errors[0]


def test_source_format_validation_blank_fails() -> None:
    errors = sv.validate_source_format(sv.normalize_source_format("  "), required=True)
    assert errors == ["source_format is required."]


def test_url_requirement_game_like_with_null_url_passes() -> None:
    payload = sources.SourceCreateRequest(
        title="In-game text",
        url=None,
        source_type="official_story",
        source_format="game",
        game="Genshin",
        reliability_tier="tier_1",
    )
    _normalized, errors = sources._normalize_source_create_payload(payload)
    assert errors == []


def test_url_requirement_in_game_text_with_null_url_passes() -> None:
    payload = sources.SourceCreateRequest(
        title="Codex entry",
        url=None,
        source_type="official_databank",
        source_format="in_game_text",
        game="HSR",
        reliability_tier="tier_1",
    )
    _normalized, errors = sources._normalize_source_create_payload(payload)
    assert errors == []


def test_url_requirement_official_page_with_null_url_fails() -> None:
    payload = sources.SourceCreateRequest(
        title="Official page",
        url=None,
        source_type="official_profile",
        source_format="official_page",
        game="Genshin Impact",
        reliability_tier="tier_1",
    )
    _normalized, errors = sources._normalize_source_create_payload(payload)
    assert any("url is required" in err for err in errors)


def test_url_requirement_wiki_with_null_url_fails() -> None:
    payload = sources.SourceCreateRequest(
        title="Wiki",
        url=None,
        source_type="community_wiki",
        source_format="wiki",
        reliability_tier="tier_2",
    )
    _normalized, errors = sources._normalize_source_create_payload(payload)
    assert any("url is required" in err for err in errors)


def test_web_like_with_valid_url_passes() -> None:
    payload = sources.SourceCreateRequest(
        title="Patch notes",
        url="https://example.com/patch",
        source_type="official_story",
        source_format="patch_notes",
        game="Honkai Impact 3",
        reliability_tier="tier_1",
    )
    _normalized, errors = sources._normalize_source_create_payload(payload)
    assert errors == []


def test_reliability_source_type_invalid_combination_fails() -> None:
    payload = sources.SourceCreateRequest(
        title="Community blog",
        url="https://example.com/blog",
        source_type="community_reference",
        source_format="article",
        reliability_tier="tier_1",
    )
    _normalized, errors = sources._normalize_source_create_payload(payload)
    assert any("invalid for source_type" in err for err in errors)


def test_reliability_source_type_valid_combination_passes() -> None:
    payload = sources.SourceCreateRequest(
        title="Internal note",
        url=None,
        source_type="internal_editorial",
        source_format="internal_note",
        reliability_tier="tier_4",
    )
    _normalized, errors = sources._normalize_source_create_payload(payload)
    assert errors == []


def test_game_normalization_aliases() -> None:
    assert normalize_primary_scope_game("HI3") == "Honkai Impact 3"
    assert normalize_primary_scope_game("HSR") == "Honkai: Star Rail"
    assert normalize_primary_scope_game("Genshin") == "Genshin Impact"
    assert normalize_primary_scope_game("GGZ") == "Gun Girls Z"
    assert normalize_primary_scope_game("Cross-title") == "Multi"
