"""Unit tests for source-asset validation and linkage helpers."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api import source_asset_validation as sav


def test_asset_type_validation_valid_passes() -> None:
    values = {
        "source_id": "SRC-GI-0001",
        "asset_type": "screenshot",
        "file_path_or_url": "./img.png",
        "locator": "profile",
        "is_primary_evidence": True,
    }
    errors = sav.validate_asset_values(values)
    assert not any("asset_type" in err for err in errors)


def test_asset_type_validation_invalid_fails() -> None:
    values = {
        "source_id": "SRC-GI-0001",
        "asset_type": "bad_type",
        "file_path_or_url": "./img.png",
        "locator": "profile",
        "is_primary_evidence": True,
    }
    errors = sav.validate_asset_values(values)
    assert any("asset_type" in err for err in errors)


def test_valid_game_linkage_passes() -> None:
    source_row = {"source_id": "SRC-GI-0001", "source_format": "game"}
    asset_values = {
        "asset_type": "screenshot",
        "file_path_or_url": "/tmp/screen.png",
        "locator": "Character Profile",
    }
    assert sav.validate_source_asset_linkage(source_row, asset_values) == []


def test_invalid_web_archive_for_game_fails() -> None:
    source_row = {"source_id": "SRC-GI-0001", "source_format": "game"}
    asset_values = {
        "asset_type": "web_archive",
        "file_path_or_url": "https://archive.org/foo",
        "locator": "entry",
    }
    errors = sav.validate_source_asset_linkage(source_row, asset_values)
    assert any("web_archive" in err and "not valid" in err for err in errors)


def test_valid_web_archive_for_wiki_with_path_passes() -> None:
    source_row = {"source_id": "SRC-WIKI-0001", "source_format": "wiki"}
    asset_values = {
        "asset_type": "web_archive",
        "file_path_or_url": "https://archive.org/snap",
        "locator": None,
    }
    assert sav.validate_source_asset_linkage(source_row, asset_values) == []


def test_web_archive_for_web_like_without_path_fails() -> None:
    source_row = {"source_id": "SRC-WIKI-0001", "source_format": "official_page"}
    asset_values = {
        "asset_type": "web_archive",
        "file_path_or_url": None,
        "locator": "entry",
    }
    errors = sav.validate_source_asset_linkage(source_row, asset_values)
    assert any("file_path_or_url is required for web_archive" in err for err in errors)


def test_video_reference_for_video_without_locator_fails() -> None:
    source_row = {"source_id": "SRC-GEN-0001", "source_format": "video"}
    asset_values = {
        "asset_type": "video_reference",
        "file_path_or_url": "https://youtube.com/watch?v=abc",
        "locator": None,
    }
    errors = sav.validate_source_asset_linkage(source_row, asset_values)
    assert any("locator is required for video_reference" in err for err in errors)


def test_file_like_without_path_fails() -> None:
    values = {
        "source_id": "SRC-GI-0001",
        "asset_type": "screenshot",
        "file_path_or_url": None,
        "locator": "profile",
        "is_primary_evidence": True,
    }
    errors = sav.validate_asset_values(values)
    assert any("file_path_or_url is required" in err for err in errors)


def test_timestamp_style_without_locator_fails() -> None:
    values = {
        "source_id": "SRC-GEN-0001",
        "asset_type": "video_reference",
        "file_path_or_url": "https://example.com/video",
        "locator": None,
        "is_primary_evidence": False,
    }
    errors = sav.validate_asset_values(values)
    assert any("locator is required" in err for err in errors)


def test_valid_manga_image_passes() -> None:
    source_row = {"source_id": "SRC-GEN-0001", "source_format": "manga"}
    asset_values = {
        "asset_type": "image",
        "file_path_or_url": "/tmp/manga.png",
        "locator": "chapter 1",
    }
    assert sav.validate_source_asset_linkage(source_row, asset_values) == []


def test_invalid_manga_audio_fails() -> None:
    source_row = {"source_id": "SRC-GEN-0001", "source_format": "manga"}
    asset_values = {
        "asset_type": "audio",
        "file_path_or_url": "/tmp/a.mp3",
        "locator": "00:01",
    }
    errors = sav.validate_source_asset_linkage(source_row, asset_values)
    assert any("not valid for source_format 'manga'" in err for err in errors)


def test_valid_internal_note_document_passes() -> None:
    source_row = {"source_id": "SRC-INT-0001", "source_format": "internal_note"}
    asset_values = {
        "asset_type": "document",
        "file_path_or_url": "/tmp/note.pdf",
        "locator": None,
    }
    assert sav.validate_source_asset_linkage(source_row, asset_values) == []


def test_source_id_pattern_and_domain_helper() -> None:
    assert sav.SOURCE_ID_PATTERN.match("SRC-GI-0001") is not None
    assert sav.SOURCE_ID_PATTERN.match("bad") is None
    assert sav.derive_asset_domain_from_source_id("SRC-GI-0001") == "GI"
    assert sav.derive_asset_domain_from_source_id("bad") is None
