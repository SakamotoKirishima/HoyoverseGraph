"""API tests for claim endpoints using TestClient + monkeypatch seams."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api import claims


class DummyConn:
    """Minimal connection stub with transaction context support."""

    @contextmanager
    def transaction(self):
        yield


class _Diag:
    def __init__(self, constraint_name: str):
        self.constraint_name = constraint_name


class FakeUniqueViolation(Exception):
    """Fake uniqueness error used for conflict-path testing."""

    def __init__(self, constraint_name: str):
        super().__init__(constraint_name)
        self.diag = _Diag(constraint_name)


@pytest.fixture()
def client() -> TestClient:
    """Test client with DB dependency overridden to use a dummy connection."""

    def _override_get_db_connection():
        yield DummyConn()

    app.dependency_overrides[claims.get_db_connection] = _override_get_db_connection
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def sample_claim_row() -> dict[str, Any]:
    return {
        "claim_id": "CLM-0121",
        "subject_entity_id": "ENT-0001",
        "predicate": "appears_in",
        "object_entity_id": "ENT-0002",
        "evidence_status": "supported",
        "confidence": 0.9,
        "source_id": "SRC-HSR-0001",
        "asset_id": "AST-HSR-0001",
        "locator": "chapter=1",
        "note": "sample note",
        "review_status": "reviewed",
        "claim_status": "active",
        "supersedes_claim_id": None,
        "contradicts_claim_id": None,
    }


@pytest.fixture()
def sample_create_payload() -> dict[str, Any]:
    return {
        "subject_entity_id": "ENT-0001",
        "predicate": "appears_in",
        "object_entity_id": "ENT-0002",
        "source_id": "SRC-HSR-0001",
        "asset_id": "AST-HSR-0001",
        "evidence_status": "supported",
        "confidence": 0.9,
        "locator": "chapter=1",
        "note": "sample note",
        "review_status": "reviewed",
        "claim_status": "active",
        "supersedes_claim_id": None,
        "contradicts_claim_id": None,
    }


def test_get_claim_valid_returns_200(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims, "_fetch_by_claim_id", lambda _c, _id: sample_claim_row)
    response = client.get("/claims/CLM-0121")
    assert response.status_code == 200
    assert response.json()["claim_id"] == "CLM-0121"


def test_get_claim_malformed_id_returns_422(client: TestClient) -> None:
    response = client.get("/claims/123")
    assert response.status_code == 422


def test_get_claim_missing_returns_404(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(claims, "_fetch_by_claim_id", lambda _c, _id: None)
    response = client.get("/claims/CLM-9999")
    assert response.status_code == 404


def test_get_claim_nested_summaries_present_when_provided(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        **sample_claim_row,
        "subject_entity": {"entity_id": "ENT-0001", "canonical_name": "Kiana"},
        "object_entity": {"entity_id": "ENT-0002", "canonical_name": "Hyperion"},
        "source": {"source_id": "SRC-HSR-0001", "title": "Story"},
        "asset": {"asset_id": "AST-HSR-0001", "asset_type": "quote"},
    }
    monkeypatch.setattr(claims, "_fetch_by_claim_id", lambda _c, _id: row)
    response = client.get("/claims/CLM-0121")
    assert response.status_code == 200
    body = response.json()
    assert body["subject_entity"]["entity_id"] == "ENT-0001"
    assert body["object_entity"]["entity_id"] == "ENT-0002"
    assert body["source"]["source_id"] == "SRC-HSR-0001"
    assert body["asset"]["asset_id"] == "AST-HSR-0001"


def test_get_claim_nullable_source_asset_handled_when_absent(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {**sample_claim_row, "source_id": None, "asset_id": None, "source": None, "asset": None}
    monkeypatch.setattr(claims, "_fetch_by_claim_id", lambda _c, _id: row)
    response = client.get("/claims/CLM-0121")
    assert response.status_code == 200
    body = response.json()
    assert body["source_id"] is None
    assert body["asset_id"] is None
    assert body["source"] is None
    assert body["asset"] is None


def test_list_claims_returns_200(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims, "_list_claims", lambda _c, **_kwargs: [sample_claim_row])
    response = client.get("/claims")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["claim_id"] == "CLM-0121"


def test_list_filter_by_predicate(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_list(_c, **kwargs):
        captured.update(kwargs)
        return [sample_claim_row]

    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])
    monkeypatch.setattr(claims, "_list_claims", _fake_list)
    response = client.get("/claims?predicate=appears_in")
    assert response.status_code == 200
    assert captured["predicate"] == "appears_in"


def test_list_filter_by_evidence_status(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_list(_c, **kwargs):
        captured.update(kwargs)
        return [sample_claim_row]

    monkeypatch.setattr(claims, "_list_claims", _fake_list)
    response = client.get("/claims?evidence_status=supported")
    assert response.status_code == 200
    assert captured["evidence_status"] == "supported"


def test_list_filter_by_confidence_min(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_list(_c, **kwargs):
        captured.update(kwargs)
        return [sample_claim_row]

    monkeypatch.setattr(claims, "_list_claims", _fake_list)
    response = client.get("/claims?confidence_min=0.6")
    assert response.status_code == 200
    assert captured["confidence_min"] == 0.6


def test_list_filter_by_confidence_max(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_list(_c, **kwargs):
        captured.update(kwargs)
        return [sample_claim_row]

    monkeypatch.setattr(claims, "_list_claims", _fake_list)
    response = client.get("/claims?confidence_max=0.9")
    assert response.status_code == 200
    assert captured["confidence_max"] == 0.9


def test_list_filter_by_confidence_bounds(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_list(_c, **kwargs):
        captured.update(kwargs)
        return [sample_claim_row]

    monkeypatch.setattr(claims, "_list_claims", _fake_list)
    response = client.get("/claims?confidence_min=0.4&confidence_max=0.8")
    assert response.status_code == 200
    assert captured["confidence_min"] == 0.4
    assert captured["confidence_max"] == 0.8


def test_list_invalid_predicate_returns_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: ["invalid predicate"])
    response = client.get("/claims?predicate=bad_pred")
    assert response.status_code == 422


def test_list_invalid_confidence_range_returns_422(client: TestClient) -> None:
    response = client.get("/claims?confidence_min=0.9&confidence_max=0.2")
    assert response.status_code == 422


def test_list_invalid_limit_offset_returns_422(client: TestClient) -> None:
    assert client.get("/claims?limit=0").status_code == 422
    assert client.get("/claims?offset=-1").status_code == 422


def test_create_valid_returns_201(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    sample_create_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims, "generate_claim_id", lambda _c: "CLM-0999")
    monkeypatch.setattr(claims, "_validate_reference_ids", lambda _c, _v: [])
    monkeypatch.setattr(
        claims,
        "_insert_claim",
        lambda _c, *, claim_id, values: {**sample_claim_row, **values, "claim_id": claim_id},
    )
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])
    response = client.post("/claims", json=sample_create_payload)
    assert response.status_code == 201
    assert response.json()["claim_id"] == "CLM-0999"


def test_create_invalid_predicate_returns_422(
    client: TestClient,
    sample_create_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: ["invalid predicate"])
    response = client.post("/claims", json=sample_create_payload)
    assert response.status_code == 422


def test_create_nonexistent_subject_entity_returns_422(
    client: TestClient,
    sample_create_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims, "generate_claim_id", lambda _c: "CLM-0999")
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])
    monkeypatch.setattr(
        claims,
        "_validate_reference_ids",
        lambda _c, _v: ["subject_entity_id 'ENT-0001' does not exist."],
    )
    response = client.post("/claims", json=sample_create_payload)
    assert response.status_code == 422


def test_create_nonexistent_object_entity_returns_422(
    client: TestClient,
    sample_create_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims, "generate_claim_id", lambda _c: "CLM-0999")
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])
    monkeypatch.setattr(
        claims,
        "_validate_reference_ids",
        lambda _c, _v: ["object_entity_id 'ENT-0002' does not exist."],
    )
    response = client.post("/claims", json=sample_create_payload)
    assert response.status_code == 422


def test_create_nonexistent_source_returns_422(
    client: TestClient,
    sample_create_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims, "generate_claim_id", lambda _c: "CLM-0999")
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])
    monkeypatch.setattr(
        claims,
        "_validate_reference_ids",
        lambda _c, _v: ["source_id 'SRC-HSR-0001' does not exist."],
    )
    response = client.post("/claims", json=sample_create_payload)
    assert response.status_code == 422


def test_create_nonexistent_asset_returns_422(
    client: TestClient,
    sample_create_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims, "generate_claim_id", lambda _c: "CLM-0999")
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])
    monkeypatch.setattr(
        claims,
        "_validate_reference_ids",
        lambda _c, _v: ["asset_id 'AST-HSR-0001' does not exist."],
    )
    response = client.post("/claims", json=sample_create_payload)
    assert response.status_code == 422


def test_create_source_asset_mismatch_returns_422(
    client: TestClient,
    sample_create_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims, "generate_claim_id", lambda _c: "CLM-0999")
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])
    monkeypatch.setattr(
        claims,
        "_validate_reference_ids",
        lambda _c, _v: [
            "asset_id 'AST-HSR-0001' belongs to source_id 'SRC-GI-0002', not 'SRC-HSR-0001'."
        ],
    )
    response = client.post("/claims", json=sample_create_payload)
    assert response.status_code == 422


def test_create_invalid_supersedes_returns_422(
    client: TestClient,
    sample_create_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {**sample_create_payload, "supersedes_claim_id": "BAD-ID"}
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])
    response = client.post("/claims", json=payload)
    assert response.status_code == 422


def test_create_invalid_contradicts_returns_422(
    client: TestClient,
    sample_create_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {**sample_create_payload, "contradicts_claim_id": "BAD-ID"}
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])
    response = client.post("/claims", json=payload)
    assert response.status_code == 422


def test_create_uniqueness_conflict_returns_409(
    client: TestClient,
    sample_create_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims.pg_errors, "UniqueViolation", FakeUniqueViolation)
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])
    monkeypatch.setattr(claims, "_validate_reference_ids", lambda _c, _v: [])
    monkeypatch.setattr(claims, "generate_claim_id", lambda _c: "CLM-0999")

    def _raise_unique(*_args, **_kwargs):
        raise FakeUniqueViolation("uq_claims_spo_source")

    monkeypatch.setattr(claims, "_insert_claim", _raise_unique)
    response = client.post("/claims", json=sample_create_payload)
    assert response.status_code == 409


def test_update_valid_partial_patch_returns_200(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims, "_fetch_by_claim_id", lambda _c, _id: dict(sample_claim_row))
    monkeypatch.setattr(claims, "_validate_reference_ids", lambda _c, _v: [])
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])
    monkeypatch.setattr(
        claims,
        "_update_claim",
        lambda _c, *, claim_id, values: {**sample_claim_row, **values, "claim_id": claim_id},
    )
    response = client.patch("/claims/CLM-0121", json={"note": "updated"})
    assert response.status_code == 200
    assert response.json()["note"] == "updated"


def test_update_omitted_fields_remain_unchanged(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_values: dict[str, Any] = {}
    monkeypatch.setattr(claims, "_fetch_by_claim_id", lambda _c, _id: dict(sample_claim_row))
    monkeypatch.setattr(claims, "_validate_reference_ids", lambda _c, _v: [])
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])

    def _fake_update(_c, *, claim_id, values):
        captured_values.update(values)
        return {**sample_claim_row, **values, "claim_id": claim_id}

    monkeypatch.setattr(claims, "_update_claim", _fake_update)
    response = client.patch("/claims/CLM-0121", json={"note": "refined"})
    assert response.status_code == 200
    assert captured_values["predicate"] == sample_claim_row["predicate"]
    assert captured_values["note"] == "refined"


def test_update_explicit_null_clears_nullable(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims, "_fetch_by_claim_id", lambda _c, _id: dict(sample_claim_row))
    monkeypatch.setattr(claims, "_validate_reference_ids", lambda _c, _v: [])
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])
    monkeypatch.setattr(
        claims,
        "_update_claim",
        lambda _c, *, claim_id, values: {**sample_claim_row, **values, "claim_id": claim_id},
    )
    response = client.patch("/claims/CLM-0121", json={"asset_id": None})
    assert response.status_code == 200
    assert response.json()["asset_id"] is None


def test_update_invalid_predicate_returns_422(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims, "_fetch_by_claim_id", lambda _c, _id: dict(sample_claim_row))
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: ["invalid predicate"])
    response = client.patch("/claims/CLM-0121", json={"predicate": "bad_pred"})
    assert response.status_code == 422


def test_update_invalid_source_asset_mismatch_returns_422(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims, "_fetch_by_claim_id", lambda _c, _id: dict(sample_claim_row))
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])
    monkeypatch.setattr(
        claims,
        "_validate_reference_ids",
        lambda _c, _v: [
            "asset_id 'AST-HSR-0001' belongs to source_id 'SRC-GI-0002', not 'SRC-HSR-0001'."
        ],
    )
    response = client.patch("/claims/CLM-0121", json={"asset_id": "AST-HSR-0001"})
    assert response.status_code == 422


def test_update_invalid_self_reference_returns_422(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims, "_fetch_by_claim_id", lambda _c, _id: dict(sample_claim_row))
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])
    response = client.patch("/claims/CLM-0121", json={"supersedes_claim_id": "CLM-0121"})
    assert response.status_code == 422


def test_update_uniqueness_conflict_returns_409(
    client: TestClient,
    sample_claim_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(claims.pg_errors, "UniqueViolation", FakeUniqueViolation)
    monkeypatch.setattr(claims, "_fetch_by_claim_id", lambda _c, _id: dict(sample_claim_row))
    monkeypatch.setattr(claims, "_validate_reference_ids", lambda _c, _v: [])
    monkeypatch.setattr(claims, "validate_predicate_usage", lambda _p: [])

    def _raise_unique(*_args, **_kwargs):
        raise FakeUniqueViolation("uq_claims_spo_source")

    monkeypatch.setattr(claims, "_update_claim", _raise_unique)
    response = client.patch("/claims/CLM-0121", json={"predicate": "appears_in"})
    assert response.status_code == 409


def test_update_nonexistent_claim_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(claims, "_fetch_by_claim_id", lambda _c, _id: None)
    response = client.patch("/claims/CLM-0121", json={"note": "x"})
    assert response.status_code == 404


def test_delete_existing_unreferenced_claim_returns_200(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(claims, "_claim_exists", lambda _c, _id: True)
    monkeypatch.setattr(claims, "_count_claim_references", lambda _c, _id: (0, 0, 0))
    monkeypatch.setattr(claims, "_delete_claim", lambda _c, _id: True)
    response = client.delete("/claims/CLM-0121")
    assert response.status_code == 200
    assert response.json() == {"deleted": True, "claim_id": "CLM-0121"}


def test_delete_nonexistent_claim_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(claims, "_claim_exists", lambda _c, _id: False)
    response = client.delete("/claims/CLM-0121")
    assert response.status_code == 404


def test_delete_referenced_claim_returns_409(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(claims, "_claim_exists", lambda _c, _id: True)
    monkeypatch.setattr(claims, "_count_claim_references", lambda _c, _id: (2, 1, 3))
    response = client.delete("/claims/CLM-0121")
    assert response.status_code == 409
    body = response.json()
    assert body["deleted"] is False
    assert body["supersedes_references"] == 2
    assert body["contradicts_references"] == 1
    assert body["total_references"] == 3
