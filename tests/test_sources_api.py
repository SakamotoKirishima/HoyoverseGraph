"""API tests for source endpoints using TestClient and monkeypatch seams."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api import sources


class DummyConn:
    """Minimal connection stub with transaction context support."""

    @contextmanager
    def transaction(self):
        yield


class _Diag:
    def __init__(self, constraint_name: str):
        self.constraint_name = constraint_name


class FakeUniqueViolation(Exception):
    """Fake uniqueness error to simulate psycopg constraint violations."""

    def __init__(self, constraint_name: str):
        super().__init__(constraint_name)
        self.diag = _Diag(constraint_name)


@pytest.fixture()
def client() -> TestClient:
    """Test client with DB dependency overridden to use a dummy connection."""

    def _override_get_db_connection():
        yield DummyConn()

    app.dependency_overrides[sources.get_db_connection] = _override_get_db_connection
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def sample_source_row() -> dict[str, Any]:
    return {
        "source_id": "SRC-GI-0001",
        "title": "Genshin Impact (in-game content)",
        "url": None,
        "source_type": "official_story",
        "source_format": "game",
        "game": "Genshin Impact",
        "scope": "primary_canon",
        "reliability_tier": "tier_1",
        "language": "en",
        "publication_date": None,
        "notes": "Primary source",
    }


@pytest.fixture()
def sample_asset_summary() -> dict[str, Any]:
    return {
        "asset_id": "AST-GI-0001",
        "asset_type": "screenshot",
        "file_path_or_url": None,
        "locator": "Character Profile: Raiden Shogun",
        "description": "Profile capture",
        "is_primary_evidence": True,
        "notes": None,
    }


@pytest.fixture()
def sample_claim_summary() -> dict[str, Any]:
    return {
        "claim_id": "CLM-9021",
        "subject_entity_id": "ENT-0807",
        "predicate": "appears_in",
        "object_entity_id": "ENT-0003",
        "asset_id": "AST-GI-0001",
        "locator": None,
        "claim_status": "active",
    }


@pytest.fixture()
def sample_provenance_claim() -> dict[str, Any]:
    return {
        "claim_id": "CLM-9021",
        "subject_entity_id": "ENT-0807",
        "predicate": "appears_in",
        "object_entity_id": "ENT-0003",
        "asset_id": "AST-GI-0001",
        "locator": None,
        "evidence_status": "official_confirmed",
        "confidence": 0.9,
        "claim_status": "active",
    }


def test_get_source_valid_returns_200(
    client: TestClient,
    sample_source_row: dict[str, Any],
    sample_asset_summary: dict[str, Any],
    sample_claim_summary: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sources, "_fetch_source_by_id", lambda _c, _id: sample_source_row)
    monkeypatch.setattr(
        sources, "_fetch_assets_by_source_id", lambda _c, _id: [sample_asset_summary]
    )
    monkeypatch.setattr(
        sources,
        "_fetch_claim_summaries_by_source_id",
        lambda _c, _id: [sample_claim_summary],
    )

    response = client.get("/sources/SRC-GI-0001")
    assert response.status_code == 200
    body = response.json()
    assert body["source_id"] == "SRC-GI-0001"
    assert body["assets"][0]["asset_id"] == "AST-GI-0001"
    assert body["claims"][0]["claim_id"] == "CLM-9021"


def test_get_source_malformed_id_returns_422(client: TestClient) -> None:
    response = client.get("/sources/123")
    assert response.status_code == 422


def test_get_source_missing_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sources, "_fetch_source_by_id", lambda _c, _id: None)
    response = client.get("/sources/SRC-GI-9999")
    assert response.status_code == 404


def test_get_source_provenance_valid_returns_200(
    client: TestClient,
    sample_source_row: dict[str, Any],
    sample_provenance_claim: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sources, "_fetch_source_by_id", lambda _c, _id: sample_source_row)
    monkeypatch.setattr(
        sources,
        "_fetch_provenance_assets_by_source_id",
        lambda _c, _id: [
            {
                "asset_id": "AST-GI-0001",
                "asset_type": "screenshot",
                "locator": "Character Profile",
                "description": "Profile capture",
                "is_primary_evidence": True,
            }
        ],
    )
    monkeypatch.setattr(
        sources,
        "_fetch_provenance_claims_by_source_id",
        lambda _c, _id: [sample_provenance_claim],
    )

    response = client.get("/sources/SRC-GI-0001/provenance")
    assert response.status_code == 200
    body = response.json()
    assert body["source_id"] == "SRC-GI-0001"
    assert set(body["claims"][0].keys()) == {
        "claim_id",
        "subject_entity_id",
        "predicate",
        "object_entity_id",
        "asset_id",
        "locator",
        "evidence_status",
        "confidence",
        "claim_status",
    }


def test_get_source_provenance_missing_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sources, "_fetch_source_by_id", lambda _c, _id: None)
    response = client.get("/sources/SRC-GI-9999/provenance")
    assert response.status_code == 404


def test_get_source_provenance_malformed_id_returns_422(client: TestClient) -> None:
    response = client.get("/sources/not-an-id/provenance")
    assert response.status_code == 422


def test_create_source_valid_returns_201(
    client: TestClient,
    sample_source_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sources, "generate_source_id", lambda _c, domain: "SRC-GI-0002")
    monkeypatch.setattr(
        sources,
        "_insert_source",
        lambda _c, *, source_id, values: {**sample_source_row, **values, "source_id": source_id},
    )

    payload = {
        "title": "Genshin Impact (in-game content)",
        "url": None,
        "source_type": "official_story",
        "source_format": "game",
        "game": "Genshin",
        "scope": "primary_canon",
        "reliability_tier": "tier_1",
        "language": "en",
        "publication_date": None,
        "notes": "Primary source",
    }
    response = client.post("/sources", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["source_id"] == "SRC-GI-0002"
    assert body["assets"] == []
    assert body["claims"] == []


def test_create_source_game_null_url_succeeds(
    client: TestClient,
    sample_source_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sources, "generate_source_id", lambda _c, domain: "SRC-HSR-0001")
    monkeypatch.setattr(
        sources,
        "_insert_source",
        lambda _c, *, source_id, values: {**sample_source_row, **values, "source_id": source_id},
    )
    payload = {
        "title": "In-game source",
        "url": None,
        "source_type": "official_databank",
        "source_format": "in_game_text",
        "game": "HSR",
        "reliability_tier": "tier_1",
    }
    response = client.post("/sources", json=payload)
    assert response.status_code == 201


def test_create_source_web_like_missing_url_fails_422(client: TestClient) -> None:
    payload = {
        "title": "Wiki page",
        "url": None,
        "source_type": "community_wiki",
        "source_format": "wiki",
        "reliability_tier": "tier_2",
    }
    response = client.post("/sources", json=payload)
    assert response.status_code == 422


def test_create_source_invalid_source_type_fails_422(client: TestClient) -> None:
    payload = {
        "title": "Bad",
        "url": "https://example.com",
        "source_type": "bad_type",
        "source_format": "article",
        "reliability_tier": "tier_3",
    }
    response = client.post("/sources", json=payload)
    assert response.status_code == 422


def test_create_source_invalid_source_format_fails_422(client: TestClient) -> None:
    payload = {
        "title": "Bad",
        "url": "https://example.com",
        "source_type": "other",
        "source_format": "bad_format",
        "reliability_tier": "tier_3",
    }
    response = client.post("/sources", json=payload)
    assert response.status_code == 422


def test_create_source_invalid_reliability_combo_fails_422(client: TestClient) -> None:
    payload = {
        "title": "Invalid combo",
        "url": "https://example.com/blog",
        "source_type": "community_reference",
        "source_format": "article",
        "reliability_tier": "tier_1",
    }
    response = client.post("/sources", json=payload)
    assert response.status_code == 422


def test_create_source_uniqueness_conflict_returns_409(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sources, "generate_source_id", lambda _c, domain: "SRC-GI-0002")
    monkeypatch.setattr(sources.pg_errors, "UniqueViolation", FakeUniqueViolation)

    def _raise(_c, *, source_id, values):
        raise FakeUniqueViolation("uq_sources_dedupe_fingerprint")

    monkeypatch.setattr(sources, "_insert_source", _raise)

    payload = {
        "title": "Genshin Impact (in-game content)",
        "url": None,
        "source_type": "official_story",
        "source_format": "game",
        "game": "Genshin Impact",
        "scope": "primary_canon",
        "reliability_tier": "tier_1",
        "language": "en",
        "publication_date": None,
        "notes": "Primary source",
    }
    response = client.post("/sources", json=payload)
    assert response.status_code == 409


def test_update_source_valid_partial_patch_returns_200(
    client: TestClient,
    sample_source_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_update(_c, *, source_id, values):
        captured.update(values)
        return {**sample_source_row, **values, "source_id": source_id}

    monkeypatch.setattr(sources, "_fetch_source_by_id", lambda _c, _id: sample_source_row)
    monkeypatch.setattr(sources, "_update_source", _fake_update)
    monkeypatch.setattr(sources, "_fetch_assets_by_source_id", lambda _c, _id: [])
    monkeypatch.setattr(sources, "_fetch_claim_summaries_by_source_id", lambda _c, _id: [])

    response = client.patch("/sources/SRC-GI-0001", json={"notes": "Updated note"})
    assert response.status_code == 200
    assert captured["title"] == sample_source_row["title"]
    assert captured["notes"] == "Updated note"


def test_update_source_explicit_null_clears_nullable_field(
    client: TestClient,
    sample_source_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sources, "_fetch_source_by_id", lambda _c, _id: sample_source_row)
    monkeypatch.setattr(
        sources,
        "_update_source",
        lambda _c, *, source_id, values: {**sample_source_row, **values, "source_id": source_id},
    )
    monkeypatch.setattr(sources, "_fetch_assets_by_source_id", lambda _c, _id: [])
    monkeypatch.setattr(sources, "_fetch_claim_summaries_by_source_id", lambda _c, _id: [])

    response = client.patch("/sources/SRC-GI-0001", json={"notes": None})
    assert response.status_code == 200
    assert response.json()["notes"] is None


def test_update_source_change_to_web_like_without_url_fails_422(
    client: TestClient,
    sample_source_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sources, "_fetch_source_by_id", lambda _c, _id: sample_source_row)
    response = client.patch("/sources/SRC-GI-0001", json={"source_format": "official_page"})
    assert response.status_code == 422


def test_update_source_invalid_source_type_or_format_fails_422(
    client: TestClient,
    sample_source_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sources, "_fetch_source_by_id", lambda _c, _id: sample_source_row)
    response = client.patch("/sources/SRC-GI-0001", json={"source_type": "bad_type"})
    assert response.status_code == 422


def test_update_source_invalid_merged_reliability_combo_fails_422(
    client: TestClient,
    sample_source_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {**sample_source_row, "reliability_tier": "tier_1"}
    monkeypatch.setattr(sources, "_fetch_source_by_id", lambda _c, _id: row)
    response = client.patch("/sources/SRC-GI-0001", json={"source_type": "community_reference"})
    assert response.status_code == 422


def test_update_source_uniqueness_conflict_returns_409(
    client: TestClient,
    sample_source_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sources, "_fetch_source_by_id", lambda _c, _id: sample_source_row)
    monkeypatch.setattr(sources.pg_errors, "UniqueViolation", FakeUniqueViolation)

    def _raise(_c, *, source_id, values):
        raise FakeUniqueViolation("uq_sources_dedupe_fingerprint")

    monkeypatch.setattr(sources, "_update_source", _raise)
    response = client.patch("/sources/SRC-GI-0001", json={"title": "New title"})
    assert response.status_code == 409


def test_update_source_nonexistent_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sources, "_fetch_source_by_id", lambda _c, _id: None)
    response = client.patch("/sources/SRC-GI-9999", json={"title": "Nope"})
    assert response.status_code == 404


def test_delete_source_unreferenced_returns_200(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sources, "_source_exists", lambda _c, _id: True)
    monkeypatch.setattr(sources, "_count_inbound_source_references", lambda _c, _id: (0, 0, 0))
    monkeypatch.setattr(sources, "_delete_source", lambda _c, _id: True)

    response = client.delete("/sources/SRC-GI-0001")
    assert response.status_code == 200
    assert response.json() == {"deleted": True, "source_id": "SRC-GI-0001"}


def test_delete_source_nonexistent_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sources, "_source_exists", lambda _c, _id: False)
    response = client.delete("/sources/SRC-GI-9999")
    assert response.status_code == 404


def test_delete_source_referenced_returns_409_with_counts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sources, "_source_exists", lambda _c, _id: True)
    monkeypatch.setattr(sources, "_count_inbound_source_references", lambda _c, _id: (2, 5, 7))

    response = client.delete("/sources/SRC-GI-0001")
    assert response.status_code == 409
    body = response.json()
    assert body["asset_references"] == 2
    assert body["claim_references"] == 5
    assert body["total_references"] == 7
