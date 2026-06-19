"""API tests for source-asset endpoints using TestClient + monkeypatch seams."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api import source_assets


class DummyConn:
    """Minimal connection stub with transaction context support."""

    @contextmanager
    def transaction(self):
        yield


class _Diag:
    def __init__(self, constraint_name: str):
        self.constraint_name = constraint_name


class FakeUniqueViolation(Exception):
    """Fake uniqueness error used for conflict path testing."""

    def __init__(self, constraint_name: str):
        super().__init__(constraint_name)
        self.diag = _Diag(constraint_name)


@pytest.fixture()
def client() -> TestClient:
    """Test client with DB dependency overridden to use a dummy connection."""

    def _override_get_db_connection():
        yield DummyConn()

    app.dependency_overrides[source_assets.get_db_connection] = _override_get_db_connection
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def sample_source_summary() -> dict[str, Any]:
    return {
        "source_id": "SRC-GI-0001",
        "title": "Genshin Impact (in-game content)",
        "source_type": "official_story",
        "source_format": "game",
        "game": "Genshin Impact",
        "scope": "primary_canon",
        "reliability_tier": "tier_1",
    }


@pytest.fixture()
def sample_asset_row() -> dict[str, Any]:
    return {
        "asset_id": "AST-GI-0001",
        "source_id": "SRC-GI-0001",
        "asset_type": "screenshot",
        "file_path_or_url": "/tmp/screen.png",
        "locator": "Character Profile: Raiden Shogun",
        "description": "Profile capture",
        "is_primary_evidence": True,
        "notes": None,
    }


@pytest.fixture()
def sample_asset_create_payload() -> dict[str, Any]:
    return {
        "source_id": "SRC-GI-0001",
        "asset_type": "screenshot",
        "file_path_or_url": "/tmp/screen.png",
        "locator": "Character Profile: Raiden Shogun",
        "description": "Profile capture",
        "is_primary_evidence": True,
        "notes": None,
    }


def test_get_source_asset_valid_returns_200(
    client: TestClient,
    sample_asset_row: dict[str, Any],
    sample_source_summary: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(source_assets, "_fetch_asset_by_id", lambda _c, _id: sample_asset_row)
    monkeypatch.setattr(source_assets, "_fetch_source_summary", lambda _c, _id: sample_source_summary)

    response = client.get("/source-assets/AST-GI-0001")
    assert response.status_code == 200
    body = response.json()
    assert body["asset_id"] == "AST-GI-0001"
    assert body["source"]["source_id"] == "SRC-GI-0001"


def test_get_source_asset_malformed_id_returns_422(client: TestClient) -> None:
    response = client.get("/source-assets/not-an-id")
    assert response.status_code == 422


def test_get_source_asset_missing_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(source_assets, "_fetch_asset_by_id", lambda _c, _id: None)
    response = client.get("/source-assets/AST-GI-9999")
    assert response.status_code == 404


def test_get_source_asset_provenance_valid_returns_200(
    client: TestClient,
    sample_asset_row: dict[str, Any],
    sample_source_summary: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(source_assets, "_fetch_asset_by_id", lambda _c, _id: sample_asset_row)
    monkeypatch.setattr(source_assets, "_fetch_source_summary", lambda _c, _id: sample_source_summary)
    monkeypatch.setattr(
        source_assets,
        "_fetch_provenance_claims_by_asset_id",
        lambda _c, _id: [
            {
                "claim_id": "CLM-9021",
                "subject_entity_id": "ENT-0807",
                "predicate": "appears_in",
                "object_entity_id": "ENT-0003",
                "source_id": "SRC-GI-0001",
                "locator": None,
                "evidence_status": "official_confirmed",
                "confidence": 0.9,
                "claim_status": "active",
            }
        ],
    )

    response = client.get("/source-assets/AST-GI-0001/provenance")
    assert response.status_code == 200
    body = response.json()
    assert body["source"]["source_id"] == "SRC-GI-0001"
    assert set(body["claims"][0].keys()) == {
        "claim_id",
        "subject_entity_id",
        "predicate",
        "object_entity_id",
        "source_id",
        "locator",
        "evidence_status",
        "confidence",
        "claim_status",
    }


def test_get_source_asset_provenance_missing_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(source_assets, "_fetch_asset_by_id", lambda _c, _id: None)
    response = client.get("/source-assets/AST-GI-9999/provenance")
    assert response.status_code == 404


def test_get_source_asset_provenance_malformed_id_returns_422(client: TestClient) -> None:
    response = client.get("/source-assets/bad/provenance")
    assert response.status_code == 422


def test_create_source_asset_valid_returns_201(
    client: TestClient,
    sample_asset_row: dict[str, Any],
    sample_source_summary: dict[str, Any],
    sample_asset_create_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(source_assets, "_fetch_source_summary", lambda _c, _id: sample_source_summary)
    monkeypatch.setattr(source_assets, "generate_asset_id", lambda _c, domain: "AST-GI-0002")
    monkeypatch.setattr(
        source_assets,
        "_insert_asset",
        lambda _c, *, asset_id, values: {**sample_asset_row, **values, "asset_id": asset_id},
    )

    response = client.post("/source-assets", json=sample_asset_create_payload)
    assert response.status_code == 201
    body = response.json()
    assert body["asset_id"] == "AST-GI-0002"


def test_create_source_asset_invalid_source_id_format_fails_422(
    client: TestClient,
    sample_asset_create_payload: dict[str, Any],
) -> None:
    payload = {**sample_asset_create_payload, "source_id": "bad"}
    response = client.post("/source-assets", json=payload)
    assert response.status_code == 422


def test_create_source_asset_nonexistent_source_id_fails_422(
    client: TestClient,
    sample_asset_create_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(source_assets, "_fetch_source_summary", lambda _c, _id: None)
    response = client.post("/source-assets", json=sample_asset_create_payload)
    assert response.status_code == 422


def test_create_source_asset_invalid_asset_type_fails_422(
    client: TestClient,
    sample_asset_create_payload: dict[str, Any],
) -> None:
    payload = {**sample_asset_create_payload, "asset_type": "bad_type"}
    response = client.post("/source-assets", json=payload)
    assert response.status_code == 422


def test_create_source_asset_invalid_linkage_fails_422(
    client: TestClient,
    sample_asset_create_payload: dict[str, Any],
    sample_source_summary: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_row = {**sample_source_summary, "source_format": "game"}
    monkeypatch.setattr(source_assets, "_fetch_source_summary", lambda _c, _id: source_row)
    payload = {
        **sample_asset_create_payload,
        "asset_type": "web_archive",
        "file_path_or_url": "https://archive.org/snap",
    }
    response = client.post("/source-assets", json=payload)
    assert response.status_code == 422


def test_create_source_asset_uniqueness_conflict_returns_409(
    client: TestClient,
    sample_asset_create_payload: dict[str, Any],
    sample_source_summary: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(source_assets, "_fetch_source_summary", lambda _c, _id: sample_source_summary)
    monkeypatch.setattr(source_assets, "generate_asset_id", lambda _c, domain: "AST-GI-0002")
    monkeypatch.setattr(source_assets.pg_errors, "UniqueViolation", FakeUniqueViolation)

    def _raise(_c, *, asset_id, values):
        raise FakeUniqueViolation("uq_source_assets_dedupe_fingerprint")

    monkeypatch.setattr(source_assets, "_insert_asset", _raise)
    response = client.post("/source-assets", json=sample_asset_create_payload)
    assert response.status_code == 409


def test_update_source_asset_valid_partial_patch_returns_200(
    client: TestClient,
    sample_asset_row: dict[str, Any],
    sample_source_summary: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_update(_c, *, asset_id, values):
        captured.update(values)
        return {**sample_asset_row, **values, "asset_id": asset_id}

    monkeypatch.setattr(source_assets, "_fetch_asset_by_id", lambda _c, _id: sample_asset_row)
    monkeypatch.setattr(source_assets, "_fetch_source_summary", lambda _c, _id: sample_source_summary)
    monkeypatch.setattr(source_assets, "_update_asset", _fake_update)

    response = client.patch("/source-assets/AST-GI-0001", json={"notes": "Updated note"})
    assert response.status_code == 200
    assert captured["source_id"] == sample_asset_row["source_id"]
    assert captured["notes"] == "Updated note"


def test_update_source_asset_incompatible_new_source_fails_422(
    client: TestClient,
    sample_asset_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incompatible_source = {
        "source_id": "SRC-INT-0001",
        "title": "Internal notes",
        "source_type": "internal_editorial",
        "source_format": "internal_note",
        "game": None,
        "scope": None,
        "reliability_tier": "tier_4",
    }

    monkeypatch.setattr(source_assets, "_fetch_asset_by_id", lambda _c, _id: sample_asset_row)
    monkeypatch.setattr(source_assets, "_fetch_source_summary", lambda _c, _id: incompatible_source)

    response = client.patch("/source-assets/AST-GI-0001", json={"source_id": "SRC-INT-0001"})
    assert response.status_code == 422


def test_update_source_asset_invalid_merged_file_locator_rule_fails_422(
    client: TestClient,
    sample_source_summary: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = {
        "asset_id": "AST-GI-0001",
        "source_id": "SRC-GI-0001",
        "asset_type": "video_reference",
        "file_path_or_url": "https://example.com/video",
        "locator": "00:10",
        "description": None,
        "is_primary_evidence": False,
        "notes": None,
    }
    monkeypatch.setattr(source_assets, "_fetch_asset_by_id", lambda _c, _id: existing)
    monkeypatch.setattr(
        source_assets,
        "_fetch_source_summary",
        lambda _c, _id: {**sample_source_summary, "source_format": "video"},
    )

    response = client.patch("/source-assets/AST-GI-0001", json={"locator": None})
    assert response.status_code == 422


def test_update_source_asset_uniqueness_conflict_returns_409(
    client: TestClient,
    sample_asset_row: dict[str, Any],
    sample_source_summary: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(source_assets, "_fetch_asset_by_id", lambda _c, _id: sample_asset_row)
    monkeypatch.setattr(source_assets, "_fetch_source_summary", lambda _c, _id: sample_source_summary)
    monkeypatch.setattr(source_assets.pg_errors, "UniqueViolation", FakeUniqueViolation)

    def _raise(_c, *, asset_id, values):
        raise FakeUniqueViolation("uq_source_assets_dedupe_fingerprint")

    monkeypatch.setattr(source_assets, "_update_asset", _raise)
    response = client.patch("/source-assets/AST-GI-0001", json={"description": "dup"})
    assert response.status_code == 409


def test_update_source_asset_nonexistent_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(source_assets, "_fetch_asset_by_id", lambda _c, _id: None)
    response = client.patch("/source-assets/AST-GI-9999", json={"notes": "Nope"})
    assert response.status_code == 404


def test_delete_source_asset_unreferenced_returns_200(
    client: TestClient,
    sample_asset_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(source_assets, "_fetch_asset_by_id", lambda _c, _id: sample_asset_row)
    monkeypatch.setattr(source_assets, "_count_claim_asset_references", lambda _c, _id: 0)
    monkeypatch.setattr(source_assets, "_delete_asset", lambda _c, _id: True)

    response = client.delete("/source-assets/AST-GI-0001")
    assert response.status_code == 200
    assert response.json() == {"deleted": True, "asset_id": "AST-GI-0001"}


def test_delete_source_asset_nonexistent_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(source_assets, "_fetch_asset_by_id", lambda _c, _id: None)
    response = client.delete("/source-assets/AST-GI-9999")
    assert response.status_code == 404


def test_delete_source_asset_referenced_returns_409(
    client: TestClient,
    sample_asset_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(source_assets, "_fetch_asset_by_id", lambda _c, _id: sample_asset_row)
    monkeypatch.setattr(source_assets, "_count_claim_asset_references", lambda _c, _id: 3)

    response = client.delete("/source-assets/AST-GI-0001")
    assert response.status_code == 409
    body = response.json()
    assert body["claim_references"] == 3
