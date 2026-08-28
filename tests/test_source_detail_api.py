"""Contract tests for the source-centric detail endpoint."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api import sources
from api.main import app


class DummyConn:
    """Minimal connection stub; query seams are monkeypatched in each test."""

    @contextmanager
    def transaction(self):
        yield


@pytest.fixture()
def client() -> TestClient:
    """Provide an API client without requiring a live PostgreSQL database."""

    def override_get_db_connection():
        yield DummyConn()

    app.dependency_overrides[sources.get_db_connection] = override_get_db_connection
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def source_row(
    source_id: str = "SRC-HI3-0001", *, publication_date: date | None = date(2026, 1, 15)
) -> dict[str, Any]:
    """Build a canonical source record with both populated and nullable fields."""
    return {
        "source_id": source_id,
        "title": "HI3 Main Story Chapter 1",
        "url": "https://example.com/hi3/chapter-1",
        "source_type": "official_story",
        "source_format": "in_game_text",
        "game": "Honkai Impact 3",
        "scope": "main_story",
        "reliability_tier": "tier_1",
        "language": "en",
        "publication_date": publication_date,
        "notes": None,
    }


def asset_row(
    asset_id: str,
    source_id: str = "SRC-HI3-0001",
    *,
    is_primary_evidence: bool | None,
) -> dict[str, Any]:
    """Build a full source asset row used by the detail fetch seam."""
    return {
        "asset_id": asset_id,
        "source_id": source_id,
        "asset_type": "screenshot",
        "file_path_or_url": None,
        "locator": f"Locator for {asset_id}",
        "description": f"Description for {asset_id}",
        "is_primary_evidence": is_primary_evidence,
        "notes": None,
    }


def claim_row(
    claim_id: str,
    *,
    subject_id: str = "ENT-0001",
    subject_name: str = "Kiana Kaslana",
    object_id: str = "ENT-0002",
    object_name: str = "Honkai Impact 3",
    asset_id: str | None = "AST-HI3-0001",
) -> dict[str, Any]:
    """Build a joined claim/entity row matching the detail query aliases."""
    return {
        "claim_id": claim_id,
        "subject_entity_id": subject_id,
        "subject_canonical_name": subject_name,
        "subject_display_label": subject_name.split()[0],
        "subject_entity_type": "character",
        "subject_primary_scope_game": "Multi",
        "predicate": "related_to",
        "object_entity_id": object_id,
        "object_canonical_name": object_name,
        "object_display_label": object_name,
        "object_entity_type": "game",
        "object_primary_scope_game": "Honkai Impact 3",
        "evidence_status": "official_confirmed",
        "confidence": 0.95,
        "asset_id": asset_id,
        "locator": "Chapter 1",
        "note": "Verified from the source.",
        "review_status": "approved",
        "claim_status": "active",
    }


def configure_detail_fetches(
    monkeypatch: pytest.MonkeyPatch,
    *,
    source: dict[str, Any] | None,
    assets: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> None:
    """Configure the three repository seams used by the thin route handler."""
    monkeypatch.setattr(sources, "_fetch_source_by_id", lambda _conn, _source_id: source)
    monkeypatch.setattr(
        sources,
        "_fetch_source_detail_assets_by_source_id",
        lambda _conn, _source_id: assets,
    )
    monkeypatch.setattr(
        sources,
        "_fetch_source_detail_claims_by_source_id",
        lambda _conn, _source_id: claims,
    )


def test_source_detail_returns_canonical_source_metadata_and_nulls(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = source_row()
    configure_detail_fetches(monkeypatch, source=source, assets=[], claims=[])

    response = client.get("/sources/SRC-HI3-0001/detail")

    assert response.status_code == 200
    assert response.json()["source"] == {
        **source,
        "publication_date": "2026-01-15",
    }


def test_source_detail_returns_unreferenced_assets_in_id_order_and_counts_only_true_primary(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assets = [
        asset_row("AST-HI3-0003", is_primary_evidence=None),
        asset_row("AST-HI3-0001", is_primary_evidence=True),
        asset_row("AST-HI3-0002", is_primary_evidence=False),
    ]
    configure_detail_fetches(monkeypatch, source=source_row(), assets=assets, claims=[])

    response = client.get("/sources/SRC-HI3-0001/detail")

    assert response.status_code == 200
    body = response.json()
    assert [asset["asset_id"] for asset in body["assets"]] == [
        "AST-HI3-0001",
        "AST-HI3-0002",
        "AST-HI3-0003",
    ]
    assert body["assets"][2]["locator"] == "Locator for AST-HI3-0003"
    assert body["assets"][2]["description"] == "Description for AST-HI3-0003"
    assert body["assets"][2]["asset_type"] == "screenshot"
    assert body["assets"][2]["is_primary_evidence"] is None
    assert body["summary"] == {
        "claim_count": 0,
        "asset_count": 3,
        "primary_evidence_asset_count": 1,
        "related_entity_count": 0,
    }


def test_source_detail_preserves_claim_direction_entity_refs_and_null_asset_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    claim = claim_row(
        "CLM-0001",
        subject_id="ENT-0009",
        subject_name="Entity A",
        object_id="ENT-0010",
        object_name="Entity B",
        asset_id=None,
    )
    configure_detail_fetches(monkeypatch, source=source_row(), assets=[], claims=[claim])

    response = client.get("/sources/SRC-HI3-0001/detail")

    assert response.status_code == 200
    returned_claim = response.json()["claims"][0]
    assert returned_claim["claim_id"] == "CLM-0001"
    assert returned_claim["subject"] == {
        "entity_id": "ENT-0009",
        "canonical_name": "Entity A",
        "display_label": "Entity",
        "entity_type": "character",
        "primary_scope_game": "Multi",
    }
    assert returned_claim["predicate"] == "related_to"
    assert returned_claim["object"] == {
        "entity_id": "ENT-0010",
        "canonical_name": "Entity B",
        "display_label": "Entity B",
        "entity_type": "game",
        "primary_scope_game": "Honkai Impact 3",
    }
    assert returned_claim["asset_id"] is None
    assert returned_claim["evidence_status"] == "official_confirmed"
    assert returned_claim["confidence"] == 0.95
    assert returned_claim["review_status"] == "approved"
    assert returned_claim["claim_status"] == "active"


def test_source_detail_empty_related_data_returns_zeroed_summary(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_detail_fetches(monkeypatch, source=source_row(), assets=[], claims=[])

    response = client.get("/sources/SRC-HI3-0001/detail")

    assert response.status_code == 200
    assert response.json() == {
        "source": {**source_row(), "publication_date": "2026-01-15"},
        "assets": [],
        "claims": [],
        "summary": {
            "claim_count": 0,
            "asset_count": 0,
            "primary_evidence_asset_count": 0,
            "related_entity_count": 0,
        },
    }


def test_source_detail_summary_counts_unique_related_entities(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    claims = [
        claim_row("CLM-0003", subject_id="ENT-A", object_id="ENT-B"),
        claim_row("CLM-0001", subject_id="ENT-A", object_id="ENT-C"),
        claim_row("CLM-0002", subject_id="ENT-C", object_id="ENT-B"),
    ]
    assets = [
        asset_row("AST-HI3-0003", is_primary_evidence=False),
        asset_row("AST-HI3-0001", is_primary_evidence=True),
        asset_row("AST-HI3-0002", is_primary_evidence=True),
    ]
    configure_detail_fetches(monkeypatch, source=source_row(), assets=assets, claims=claims)

    response = client.get("/sources/SRC-HI3-0001/detail")

    assert response.status_code == 200
    body = response.json()
    assert [claim["claim_id"] for claim in body["claims"]] == [
        "CLM-0001",
        "CLM-0002",
        "CLM-0003",
    ]
    assert [asset["asset_id"] for asset in body["assets"]] == [
        "AST-HI3-0001",
        "AST-HI3-0002",
        "AST-HI3-0003",
    ]
    assert body["summary"] == {
        "claim_count": 3,
        "asset_count": 3,
        "primary_evidence_asset_count": 2,
        "related_entity_count": 3,
    }


def test_source_detail_excludes_other_source_data(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_a = source_row("SRC-HI3-0001")
    source_b = source_row("SRC-HI3-0002")
    assets_by_source = {
        source_a["source_id"]: [asset_row("AST-HI3-0001", source_a["source_id"], is_primary_evidence=True)],
        source_b["source_id"]: [asset_row("AST-HI3-0002", source_b["source_id"], is_primary_evidence=True)],
    }
    claims_by_source = {
        source_a["source_id"]: [claim_row("CLM-0001")],
        source_b["source_id"]: [claim_row("CLM-0002")],
    }
    monkeypatch.setattr(
        sources,
        "_fetch_source_by_id",
        lambda _conn, source_id: {source_a["source_id"]: source_a, source_b["source_id"]: source_b}.get(
            source_id
        ),
    )
    monkeypatch.setattr(
        sources,
        "_fetch_source_detail_assets_by_source_id",
        lambda _conn, source_id: assets_by_source[source_id],
    )
    monkeypatch.setattr(
        sources,
        "_fetch_source_detail_claims_by_source_id",
        lambda _conn, source_id: claims_by_source[source_id],
    )

    response = client.get("/sources/SRC-HI3-0001/detail")

    assert response.status_code == 200
    body = response.json()
    assert body["source"]["source_id"] == "SRC-HI3-0001"
    assert [asset["asset_id"] for asset in body["assets"]] == ["AST-HI3-0001"]
    assert [claim["claim_id"] for claim in body["claims"]] == ["CLM-0001"]


def test_source_detail_dedupes_join_multiplied_rows(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assets = [
        asset_row("AST-HI3-0001", is_primary_evidence=True),
        asset_row("AST-HI3-0002", is_primary_evidence=False),
    ]
    claims = [claim_row("CLM-0001"), claim_row("CLM-0002")]
    configure_detail_fetches(
        monkeypatch,
        source=source_row(),
        assets=[assets[0], assets[1], assets[0], assets[1]],
        claims=[claims[0], claims[1], claims[0], claims[1]],
    )

    response = client.get("/sources/SRC-HI3-0001/detail")

    assert response.status_code == 200
    body = response.json()
    assert len(body["assets"]) == 2
    assert len(body["claims"]) == 2
    assert body["summary"]["asset_count"] == 2
    assert body["summary"]["claim_count"] == 2


def test_source_detail_malformed_id_returns_default_validation_error(client: TestClient) -> None:
    response = client.get("/sources/not-a-source/detail")

    assert response.status_code == 422
    assert "detail" in response.json()


def test_source_detail_missing_source_returns_existing_error_shape(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_detail_fetches(monkeypatch, source=None, assets=[], claims=[])

    response = client.get("/sources/SRC-HI3-9999/detail")

    assert response.status_code == 404
    assert response.json() == {"detail": "Source not found for id 'SRC-HI3-9999'."}
