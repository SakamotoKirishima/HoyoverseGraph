"""API tests for entity endpoints using FastAPI TestClient and monkeypatches."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.main import app
from api import entities


class DummyConn:
    """Minimal connection stub with transaction context support."""

    @contextmanager
    def transaction(self):
        yield


class _Diag:
    def __init__(self, constraint_name: str):
        self.constraint_name = constraint_name


class FakeUniqueViolation(Exception):
    """Fake unique violation used to simulate DB uniqueness errors."""

    def __init__(self, constraint_name: str):
        super().__init__(constraint_name)
        self.diag = _Diag(constraint_name)


@pytest.fixture()
def client() -> TestClient:
    """Create test client with DB dependency overridden by a dummy connection."""

    def _override_get_db_connection():
        yield DummyConn()

    app.dependency_overrides[entities.get_db_connection] = _override_get_db_connection
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def sample_entity_row() -> dict[str, Any]:
    return {
        "entity_id": "ENT-0121",
        "canonical_name": "Raiden Shogun",
        "entity_type": "character",
        "primary_scope_game": "Genshin Impact",
        "display_label": "Raiden Shogun",
        "aliases_pipe_delimited": "Ei|Raiden Ei",
        "short_description": "Electro Archon of Inazuma.",
        "starter_status": "seed",
        "notes": "...",
    }


def test_get_by_valid_entity_id_returns_200(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entities, "_fetch_by_entity_id", lambda _c, _id: sample_entity_row)
    response = client.get("/entities/ENT-0121")
    assert response.status_code == 200
    body = response.json()
    assert body["entity_id"] == "ENT-0121"
    assert body["slug"] == "raiden-shogun"


def test_get_by_malformed_entity_id_returns_422(client: TestClient) -> None:
    response = client.get("/entities/123")
    assert response.status_code == 422


def test_get_by_missing_entity_id_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(entities, "_fetch_by_entity_id", lambda _c, _id: None)
    response = client.get("/entities/ENT-9999")
    assert response.status_code == 404


def test_get_by_slug_returns_200(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entities, "_fetch_by_slug", lambda _c, _s: [sample_entity_row])
    response = client.get("/entities/slug/raiden-shogun")
    assert response.status_code == 200
    assert response.json()["entity_id"] == "ENT-0121"


def test_get_by_slug_missing_returns_404(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entities, "_fetch_by_slug", lambda _c, _s: [])
    response = client.get("/entities/slug/missing-slug")
    assert response.status_code == 404


def test_get_by_slug_ambiguous_returns_409(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row2 = dict(sample_entity_row)
    row2["entity_id"] = "ENT-0122"
    monkeypatch.setattr(entities, "_fetch_by_slug", lambda _c, _s: [sample_entity_row, row2])
    response = client.get("/entities/slug/raiden-shogun")
    assert response.status_code == 409


def test_lookup_resolves_canonical_display(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entities, "_fetch_by_canonical_or_display", lambda _c, _v: [sample_entity_row])
    monkeypatch.setattr(entities, "_fetch_by_slug", lambda _c, _s: [])
    response = client.get("/entities/lookup/Raiden%20Shogun")
    assert response.status_code == 200
    assert response.json()["entity_id"] == "ENT-0121"


def test_lookup_falls_back_to_slug(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entities, "_fetch_by_canonical_or_display", lambda _c, _v: [])
    monkeypatch.setattr(entities, "_fetch_by_slug", lambda _c, _s: [sample_entity_row])
    response = client.get("/entities/lookup/raiden-shogun")
    assert response.status_code == 200
    assert response.json()["entity_id"] == "ENT-0121"


def test_lookup_ambiguous_returns_409(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row2 = dict(sample_entity_row)
    row2["entity_id"] = "ENT-0999"
    monkeypatch.setattr(entities, "_fetch_by_canonical_or_display", lambda _c, _v: [sample_entity_row, row2])
    response = client.get("/entities/lookup/Raiden%20Shogun")
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "matches" in detail


def test_list_entities_returns_200(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entities, "get_allowed_entity_types", lambda: {"character"})
    monkeypatch.setattr(
        entities,
        "_list_entities",
        lambda _c, **_kwargs: [sample_entity_row],
    )
    response = client.get("/entities")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["aliases"] == ["Ei", "Raiden Ei"]
    assert "aliases_pipe_delimited" not in body[0]


def test_list_filter_by_entity_type(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_list(_c, **kwargs):
        captured.update(kwargs)
        return [sample_entity_row]

    monkeypatch.setattr(entities, "get_allowed_entity_types", lambda: {"character"})
    monkeypatch.setattr(entities, "_list_entities", _fake_list)
    response = client.get("/entities?entity_type=character")
    assert response.status_code == 200
    assert captured["entity_type"] == "character"


def test_list_filter_by_primary_scope_game_alias(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_list(_c, **kwargs):
        captured.update(kwargs)
        return [sample_entity_row]

    monkeypatch.setattr(entities, "get_allowed_entity_types", lambda: {"character"})
    monkeypatch.setattr(entities, "_list_entities", _fake_list)
    response = client.get("/entities?primary_scope_game=HSR")
    assert response.status_code == 200
    assert captured["primary_scope_game"] == "Honkai: Star Rail"


def test_list_filter_by_both(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_list(_c, **kwargs):
        captured.update(kwargs)
        return [sample_entity_row]

    monkeypatch.setattr(entities, "get_allowed_entity_types", lambda: {"character"})
    monkeypatch.setattr(entities, "_list_entities", _fake_list)
    response = client.get("/entities?entity_type=character&primary_scope_game=Genshin")
    assert response.status_code == 200
    assert captured["entity_type"] == "character"
    assert captured["primary_scope_game"] == "Genshin Impact"


def test_list_invalid_primary_scope_game_returns_422(client: TestClient) -> None:
    response = client.get("/entities?primary_scope_game=NotAGame")
    assert response.status_code == 422


def test_list_invalid_limit_offset_returns_422(client: TestClient) -> None:
    assert client.get("/entities?limit=0").status_code == 422
    assert client.get("/entities?offset=-1").status_code == 422


def test_create_valid_returns_201(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entities, "generate_entity_id", lambda _c: "ENT-0999")
    monkeypatch.setattr(
        entities,
        "_insert_entity",
        lambda _c, *, entity_id, values: {
            **sample_entity_row,
            **values,
            "entity_id": entity_id,
        },
    )
    payload = {
        "canonical_name": "Raiden Shogun",
        "entity_type": "character",
        "primary_scope_game": "Genshin",
        "display_label": "Raiden Shogun",
        "aliases": ["Ei", "Raiden Ei"],
        "short_description": "Electro Archon of Inazuma.",
        "starter_status": "seed",
        "notes": "...",
    }
    response = client.post("/entities", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["entity_id"] == "ENT-0999"
    assert body["aliases"] == ["Ei", "Raiden Ei"]
    assert "aliases_pipe_delimited" not in body


def test_create_invalid_starter_status_returns_422(client: TestClient) -> None:
    payload = {"canonical_name": "X", "entity_type": "character", "starter_status": "draft"}
    response = client.post("/entities", json=payload)
    assert response.status_code == 422


def test_create_invalid_primary_scope_game_returns_422(client: TestClient) -> None:
    payload = {"canonical_name": "X", "entity_type": "character", "primary_scope_game": "Nope"}
    response = client.post("/entities", json=payload)
    assert response.status_code == 422


def test_create_duplicate_returns_409(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(entities.pg_errors, "UniqueViolation", FakeUniqueViolation)
    monkeypatch.setattr(entities, "generate_entity_id", lambda _c: "ENT-1000")

    def _raise_unique(*_args, **_kwargs):
        raise FakeUniqueViolation("uq_entities_canonical_name_entity_type")

    monkeypatch.setattr(entities, "_insert_entity", _raise_unique)
    payload = {"canonical_name": "Raiden Shogun", "entity_type": "character"}
    response = client.post("/entities", json=payload)
    assert response.status_code == 409


def test_update_valid_partial_patch_returns_200(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entities, "_fetch_by_entity_id", lambda _c, _id: dict(sample_entity_row))
    monkeypatch.setattr(
        entities,
        "_update_entity",
        lambda _c, *, entity_id, values: {**sample_entity_row, **values, "entity_id": entity_id},
    )
    response = client.patch("/entities/ENT-0121", json={"starter_status": "candidate"})
    assert response.status_code == 200
    assert response.json()["starter_status"] == "candidate"


def test_update_omitted_fields_remain_unchanged(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_values: dict[str, Any] = {}

    monkeypatch.setattr(entities, "_fetch_by_entity_id", lambda _c, _id: dict(sample_entity_row))

    def _fake_update(_c, *, entity_id, values):
        captured_values.update(values)
        return {**sample_entity_row, **values, "entity_id": entity_id}

    monkeypatch.setattr(entities, "_update_entity", _fake_update)
    response = client.patch("/entities/ENT-0121", json={"notes": "Refined"})
    assert response.status_code == 200
    assert captured_values["canonical_name"] == sample_entity_row["canonical_name"]
    assert captured_values["notes"] == "Refined"


def test_update_explicit_null_clears_nullable(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entities, "_fetch_by_entity_id", lambda _c, _id: dict(sample_entity_row))
    monkeypatch.setattr(
        entities,
        "_update_entity",
        lambda _c, *, entity_id, values: {**sample_entity_row, **values, "entity_id": entity_id},
    )
    response = client.patch("/entities/ENT-0121", json={"notes": None})
    assert response.status_code == 200
    assert response.json()["notes"] is None


def test_update_invalid_patch_returns_422(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entities, "_fetch_by_entity_id", lambda _c, _id: dict(sample_entity_row))
    response = client.patch("/entities/ENT-0121", json={"starter_status": "draft"})
    assert response.status_code == 422


def test_update_uniqueness_conflict_returns_409(
    client: TestClient,
    sample_entity_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entities.pg_errors, "UniqueViolation", FakeUniqueViolation)
    monkeypatch.setattr(entities, "_fetch_by_entity_id", lambda _c, _id: dict(sample_entity_row))

    def _raise_unique(*_args, **_kwargs):
        raise FakeUniqueViolation("uq_entities_canonical_name_entity_type")

    monkeypatch.setattr(entities, "_update_entity", _raise_unique)
    response = client.patch("/entities/ENT-0121", json={"canonical_name": "Other"})
    assert response.status_code == 409


def test_update_nonexistent_returns_404(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entities, "_fetch_by_entity_id", lambda _c, _id: None)
    response = client.patch("/entities/ENT-0121", json={"notes": "x"})
    assert response.status_code == 404


def test_delete_existing_unreferenced_returns_200(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(entities, "_entity_exists", lambda _c, _id: True)
    monkeypatch.setattr(entities, "_count_claim_references", lambda _c, _id: (0, 0, 0))
    monkeypatch.setattr(entities, "_delete_entity", lambda _c, _id: True)
    response = client.delete("/entities/ENT-0121")
    assert response.status_code == 200
    assert response.json() == {"deleted": True, "entity_id": "ENT-0121"}


def test_delete_nonexistent_returns_404(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entities, "_entity_exists", lambda _c, _id: False)
    response = client.delete("/entities/ENT-0121")
    assert response.status_code == 404


def test_delete_referenced_returns_409(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entities, "_entity_exists", lambda _c, _id: True)
    monkeypatch.setattr(entities, "_count_claim_references", lambda _c, _id: (3, 2, 5))
    response = client.delete("/entities/ENT-0121")
    assert response.status_code == 409
    body = response.json()
    assert body["deleted"] is False
    assert body["subject_references"] == 3
    assert body["object_references"] == 2
    assert body["total_references"] == 5
