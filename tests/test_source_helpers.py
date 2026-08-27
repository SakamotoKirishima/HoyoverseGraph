"""Unit tests for source validation and normalization helpers."""

from __future__ import annotations

import pytest

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


@pytest.mark.parametrize("source_format", ["article", "video", "trailer"])
def test_url_requirement_web_like_formats_with_null_url_fail(source_format: str) -> None:
    payload = sources.SourceCreateRequest(
        title="Web-like source",
        url=None,
        source_type="other",
        source_format=source_format,
        reliability_tier="tier_3",
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


def test_source_detail_asset_dedupe_and_sort() -> None:
    asset_rows = [
        {
            "asset_id": "AST-HI3-0002",
            "source_id": "SRC-HI3-0001",
            "asset_type": "document",
            "file_path_or_url": None,
            "locator": "Appendix",
            "description": "Secondary evidence",
            "is_primary_evidence": False,
            "notes": None,
        },
        {
            "asset_id": "AST-HI3-0001",
            "source_id": "SRC-HI3-0001",
            "asset_type": "screenshot",
            "file_path_or_url": None,
            "locator": "Chapter 1, scene X",
            "description": "Story evidence screenshot",
            "is_primary_evidence": True,
            "notes": None,
        },
        {
            "asset_id": "AST-HI3-0001",
            "source_id": "SRC-HI3-0001",
            "asset_type": "screenshot",
            "file_path_or_url": None,
            "locator": "Chapter 1, scene X",
            "description": "Story evidence screenshot",
            "is_primary_evidence": True,
            "notes": None,
        },
    ]

    assets = sources._dedupe_source_detail_assets(asset_rows)

    assert [asset.asset_id for asset in assets] == ["AST-HI3-0001", "AST-HI3-0002"]


def test_source_detail_claim_dedupe_sort_and_summary() -> None:
    claim_rows = [
        {
            "claim_id": "CLM-0002",
            "subject_entity_id": "ENT-0001",
            "subject_canonical_name": "Honkai Impact 3",
            "subject_display_label": "Honkai Impact 3",
            "subject_entity_type": "game",
            "subject_primary_scope_game": "Honkai Impact 3",
            "predicate": "features",
            "object_entity_id": "ENT-0804",
            "object_canonical_name": "Kiana Kaslana",
            "object_display_label": "Kiana",
            "object_entity_type": "character",
            "object_primary_scope_game": "Multi",
            "evidence_status": "official_confirmed",
            "confidence": 1.0,
            "asset_id": None,
            "locator": "Chapter 2",
            "note": None,
            "review_status": "approved",
            "claim_status": "active",
        },
        {
            "claim_id": "CLM-0001",
            "subject_entity_id": "ENT-0804",
            "subject_canonical_name": "Kiana Kaslana",
            "subject_display_label": "Kiana",
            "subject_entity_type": "character",
            "subject_primary_scope_game": "Multi",
            "predicate": "appears_in",
            "object_entity_id": "ENT-0001",
            "object_canonical_name": "Honkai Impact 3",
            "object_display_label": "Honkai Impact 3",
            "object_entity_type": "game",
            "object_primary_scope_game": "Honkai Impact 3",
            "evidence_status": "official_confirmed",
            "confidence": 1.0,
            "asset_id": "AST-HI3-0001",
            "locator": "Chapter 1",
            "note": None,
            "review_status": "approved",
            "claim_status": "active",
        },
        {
            "claim_id": "CLM-0001",
            "subject_entity_id": "ENT-0804",
            "subject_canonical_name": "Kiana Kaslana",
            "subject_display_label": "Kiana",
            "subject_entity_type": "character",
            "subject_primary_scope_game": "Multi",
            "predicate": "appears_in",
            "object_entity_id": "ENT-0001",
            "object_canonical_name": "Honkai Impact 3",
            "object_display_label": "Honkai Impact 3",
            "object_entity_type": "game",
            "object_primary_scope_game": "Honkai Impact 3",
            "evidence_status": "official_confirmed",
            "confidence": 1.0,
            "asset_id": "AST-HI3-0001",
            "locator": "Chapter 1",
            "note": None,
            "review_status": "approved",
            "claim_status": "active",
        },
    ]
    assets = [
        sources.SourceDetailAsset(
            asset_id="AST-HI3-0001",
            source_id="SRC-HI3-0001",
            asset_type="screenshot",
            file_path_or_url=None,
            locator="Chapter 1, scene X",
            description="Story evidence screenshot",
            is_primary_evidence=True,
            notes=None,
        ),
        sources.SourceDetailAsset(
            asset_id="AST-HI3-0002",
            source_id="SRC-HI3-0001",
            asset_type="document",
            file_path_or_url=None,
            locator="Appendix",
            description="Secondary evidence",
            is_primary_evidence=False,
            notes=None,
        ),
    ]

    claims = sources._dedupe_source_detail_claims(claim_rows)
    summary = sources._build_source_detail_summary(claims, assets)

    assert [claim.claim_id for claim in claims] == ["CLM-0001", "CLM-0002"]
    assert claims[0].subject.canonical_name == "Kiana Kaslana"
    assert claims[0].subject.display_label == "Kiana"
    assert claims[0].object.canonical_name == "Honkai Impact 3"
    assert claims[1].asset_id is None
    assert summary.model_dump() == {
        "claim_count": 2,
        "asset_count": 2,
        "primary_evidence_asset_count": 1,
        "related_entity_count": 2,
    }
