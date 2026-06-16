"""Unit tests for entity validation and helper utilities."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api import entity_validation as ev
from api import entities


def test_slugify_basic() -> None:
    assert entities._slugify("Raiden Shogun") == "raiden-shogun"


def test_slugify_with_punctuation() -> None:
    assert entities._slugify("Kiana Kaslana (St. Freya)") == "kiana-kaslana-st-freya"


def test_normalize_aliases_trim_and_dedupe_preserve_order() -> None:
    aliases = [" Ei ", "Raiden Ei", "", "ei", "  "]
    assert ev.normalize_aliases(aliases) == ["Ei", "Raiden Ei"]


def test_serialize_deserialize_aliases_roundtrip() -> None:
    serialized = ev.serialize_aliases([" Ei ", "Raiden Ei", "ei"])
    assert serialized == "Ei|Raiden Ei"
    assert ev.deserialize_aliases(serialized) == ["Ei", "Raiden Ei"]


def test_primary_scope_game_alias_normalization() -> None:
    assert ev.normalize_primary_scope_game("HI3") == "Honkai Impact 3"
    assert ev.normalize_primary_scope_game("HSR") == "Honkai: Star Rail"
    assert ev.normalize_primary_scope_game("Genshin") == "Genshin Impact"
    assert ev.normalize_primary_scope_game("GGZ") == "Gun Girls Z"
    assert ev.normalize_primary_scope_game("Cross-title") == "Multi"


def test_validate_create_payload_invalid_game() -> None:
    payload = {
        "canonical_name": "Raiden Shogun",
        "entity_type": "character",
        "primary_scope_game": "Not A Game",
    }
    _normalized, errors = ev.validate_entity_payload_for_create(payload)
    assert any("primary_scope_game must be one of" in err for err in errors)


def test_validate_create_payload_invalid_starter_status() -> None:
    payload = {
        "canonical_name": "Raiden Shogun",
        "entity_type": "character",
        "starter_status": "draft",
    }
    _normalized, errors = ev.validate_entity_payload_for_create(payload)
    assert any("starter_status must be one of" in err for err in errors)


def test_validate_create_payload_normalization() -> None:
    payload = {
        "canonical_name": "  Raiden Shogun  ",
        "entity_type": " character ",
        "display_label": "  ",
        "aliases": [" Ei ", "", "Ei", "Raiden Ei"],
        "short_description": "  Archon  ",
        "starter_status": " seed ",
        "notes": "",
    }
    normalized, errors = ev.validate_entity_payload_for_create(payload)
    assert errors == []
    assert normalized["canonical_name"] == "Raiden Shogun"
    assert normalized["entity_type"] == "character"
    assert normalized["display_label"] is None
    assert normalized["aliases_pipe_delimited"] == "Ei|Raiden Ei"
    assert normalized["short_description"] == "Archon"
    assert normalized["starter_status"] == "seed"
    assert normalized["notes"] is None


def test_validate_patch_payload_rules() -> None:
    patch_payload = {
        "canonical_name": "   ",
        "aliases": [" Ei ", "", "Ei"],
    }
    normalized, errors = ev.validate_entity_patch_payload(patch_payload)
    assert normalized["aliases_pipe_delimited"] == "Ei"
    assert "canonical_name cannot be blank." in errors
