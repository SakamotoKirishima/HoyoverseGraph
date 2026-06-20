"""API tests for graph endpoint behavior using TestClient + monkeypatch seams."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api import graph
from api.main import app


class DummyConn:
    """Minimal connection stub with transaction context support."""

    @contextmanager
    def transaction(self):
        yield


@pytest.fixture()
def client() -> TestClient:
    """Test client with DB dependency overridden to use a dummy connection."""

    def _override_get_db_connection():
        yield DummyConn()

    app.dependency_overrides[graph.get_db_connection] = _override_get_db_connection
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def sample_seed_row() -> dict[str, Any]:
    return {
        "entity_id": "ENT-0121",
        "canonical_name": "Raiden Shogun",
        "entity_type": "character",
        "primary_scope_game": "Genshin Impact",
        "display_label": "Raiden Shogun",
        "short_description": "Electro Archon of Inazuma.",
    }


@pytest.fixture()
def sample_neighbor_row() -> dict[str, Any]:
    return {
        "entity_id": "ENT-0003",
        "canonical_name": "Inazuma",
        "entity_type": "location",
        "primary_scope_game": "Genshin Impact",
        "display_label": "Inazuma",
        "short_description": "Nation of eternity.",
    }


@pytest.fixture()
def sample_edge_row() -> dict[str, Any]:
    return {
        "claim_id": "CLM-9021",
        "subject_entity_id": "ENT-0121",
        "predicate": "appears_in",
        "object_entity_id": "ENT-0003",
        "evidence_status": "official_confirmed",
        "confidence": 0.9,
        "source_id": "SRC-GI-0001",
        "asset_id": "AST-GI-0001",
        "claim_status": "active",
    }


def test_graph_depth_1_success(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    sample_edge_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)

    def _fake_fetch_claim_edges(_c, **kwargs):
        assert kwargs["touching_entity_ids"] == {"ENT-0121"}
        assert kwargs["predicate"] is None
        assert kwargs["confidence_min"] is None
        assert kwargs["evidence_status"] is None
        return [sample_edge_row]

    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [sample_seed_row, sample_neighbor_row],
    )

    response = client.get("/graph?seed_entity_id=ENT-0121&depth=1")
    assert response.status_code == 200
    body = response.json()
    assert body["seed_entity_id"] == "ENT-0121"
    assert body["depth"] == 1
    assert [node["entity_id"] for node in body["nodes"]] == ["ENT-0003", "ENT-0121"]
    assert body["edges"][0]["claim_id"] == "CLM-9021"
    assert body["edges"][0]["source"] == "ENT-0121"
    assert body["edges"][0]["target"] == "ENT-0003"


def test_graph_without_predicate_returns_all_connected_predicates(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    sample_edge_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_edge = {
        "claim_id": "CLM-9022",
        "subject_entity_id": "ENT-0003",
        "predicate": "part_of",
        "object_entity_id": "ENT-0121",
        "evidence_status": "official_confirmed",
        "confidence": 0.8,
        "source_id": "SRC-GI-0001",
        "asset_id": None,
        "claim_status": "active",
    }

    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)
    monkeypatch.setattr(
        graph,
        "_fetch_claim_edges",
        lambda _c, **_kwargs: [sample_edge_row, second_edge],
    )
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [sample_seed_row, sample_neighbor_row],
    )

    response = client.get("/graph?seed_entity_id=ENT-0121&depth=1")
    assert response.status_code == 200
    body = response.json()
    assert [edge["predicate"] for edge in body["edges"]] == ["appears_in", "part_of"]


def test_graph_depth_2_success(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    sample_edge_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_neighbor = {
        "entity_id": "ENT-0099",
        "canonical_name": "Teyvat",
        "entity_type": "world",
        "primary_scope_game": "Genshin Impact",
        "display_label": "Teyvat",
        "short_description": "The world of Genshin Impact.",
    }
    second_edge = {
        "claim_id": "CLM-9022",
        "subject_entity_id": "ENT-0003",
        "predicate": "part_of",
        "object_entity_id": "ENT-0099",
        "evidence_status": "official_confirmed",
        "confidence": 0.8,
        "source_id": "SRC-GI-0001",
        "asset_id": None,
        "claim_status": "active",
    }

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)

    calls: list[set[str]] = []

    def _fake_fetch_claim_edges(_c, **kwargs):
        calls.append(set(kwargs["touching_entity_ids"]))
        if kwargs["touching_entity_ids"] == {"ENT-0121"}:
            return [sample_edge_row]
        return [second_edge]

    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [sample_seed_row, sample_neighbor_row, second_neighbor],
    )

    response = client.get("/graph?seed_entity_id=ENT-0121&depth=2")
    assert response.status_code == 200
    body = response.json()
    assert len(body["edges"]) == 2
    assert [edge["claim_id"] for edge in body["edges"]] == ["CLM-9021", "CLM-9022"]
    assert calls == [{"ENT-0121"}, {"ENT-0003"}]


def test_graph_depth_2_does_not_expand_beyond_second_hop(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_edge_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_edge = {
        "claim_id": "CLM-9022",
        "subject_entity_id": "ENT-0003",
        "predicate": "part_of",
        "object_entity_id": "ENT-0099",
        "evidence_status": "official_confirmed",
        "confidence": 0.8,
        "source_id": "SRC-GI-0001",
        "asset_id": None,
        "claim_status": "active",
    }
    third_hop_entity = {
        "entity_id": "ENT-0100",
        "canonical_name": "Celestia",
        "entity_type": "location",
        "primary_scope_game": "Genshin Impact",
        "display_label": "Celestia",
        "short_description": "A third-hop entity that should not appear.",
    }

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)

    calls: list[set[str]] = []

    def _fake_fetch_claim_edges(_c, **kwargs):
        calls.append(set(kwargs["touching_entity_ids"]))
        if kwargs["touching_entity_ids"] == {"ENT-0121"}:
            return [sample_edge_row]
        if kwargs["touching_entity_ids"] == {"ENT-0003"}:
            return [second_edge]
        return [
            {
                "claim_id": "CLM-9999",
                "subject_entity_id": "ENT-0099",
                "predicate": "leads_to",
                "object_entity_id": "ENT-0100",
                "evidence_status": "official_confirmed",
                "confidence": 0.7,
                "source_id": "SRC-GI-0001",
                "asset_id": None,
                "claim_status": "active",
            }
        ]

    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)

    def _fake_fetch_entities_by_ids(_c, entity_ids):
        assert set(entity_ids) == {"ENT-0121", "ENT-0003", "ENT-0099"}
        return [
            sample_seed_row,
            {
                "entity_id": "ENT-0003",
                "canonical_name": "Inazuma",
                "entity_type": "location",
                "primary_scope_game": "Genshin Impact",
                "display_label": "Inazuma",
                "short_description": "Nation of eternity.",
            },
            {
                "entity_id": "ENT-0099",
                "canonical_name": "Teyvat",
                "entity_type": "world",
                "primary_scope_game": "Genshin Impact",
                "display_label": "Teyvat",
                "short_description": "The world of Genshin Impact.",
            },
        ]

    monkeypatch.setattr(graph, "_fetch_entities_by_ids", _fake_fetch_entities_by_ids)

    response = client.get("/graph?seed_entity_id=ENT-0121&depth=2")
    assert response.status_code == 200
    body = response.json()
    assert [edge["claim_id"] for edge in body["edges"]] == ["CLM-9021", "CLM-9022"]
    assert "ENT-0100" not in [node["entity_id"] for node in body["nodes"]]
    assert calls == [{"ENT-0121"}, {"ENT-0003"}]


def test_graph_seed_not_found_returns_404(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: None)
    response = client.get("/graph?seed_entity_id=ENT-9999")
    assert response.status_code == 404


def test_graph_invalid_seed_id_returns_422(client: TestClient) -> None:
    response = client.get("/graph?seed_entity_id=123")
    assert response.status_code == 422


def test_graph_invalid_depth_returns_422(client: TestClient) -> None:
    response = client.get("/graph?seed_entity_id=ENT-0121&depth=3")
    assert response.status_code == 422


def test_graph_invalid_confidence_min_returns_422(client: TestClient) -> None:
    response = client.get("/graph?seed_entity_id=ENT-0121&confidence_min=1.5")
    assert response.status_code == 422


def test_graph_confidence_min_below_zero_returns_422(client: TestClient) -> None:
    response = client.get("/graph?seed_entity_id=ENT-0121&confidence_min=-0.1")
    assert response.status_code == 422


def test_graph_predicate_filter_is_passed(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_fetch_claim_edges(_c, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)
    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    monkeypatch.setattr(graph, "_fetch_entities_by_ids", lambda _c, _ids: [sample_seed_row])

    response = client.get("/graph?seed_entity_id=ENT-0121&predicate=appears_in")
    assert response.status_code == 200
    assert captured["predicate"] == "appears_in"


def test_graph_predicate_filter_applies_at_depth_1(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    sample_edge_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    filtered_edge = {
        "claim_id": "CLM-9999",
        "subject_entity_id": "ENT-0121",
        "predicate": "member_of",
        "object_entity_id": "ENT-0003",
        "evidence_status": "official_confirmed",
        "confidence": 0.7,
        "source_id": None,
        "asset_id": None,
        "claim_status": "active",
    }

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)

    def _fake_fetch_claim_edges(_c, **kwargs):
        assert kwargs["predicate"] == "appears_in"
        return [sample_edge_row]

    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [sample_seed_row, sample_neighbor_row],
    )

    response = client.get("/graph?seed_entity_id=ENT-0121&depth=1&predicate=appears_in")
    assert response.status_code == 200
    body = response.json()
    assert [edge["claim_id"] for edge in body["edges"]] == ["CLM-9021"]
    assert filtered_edge["claim_id"] not in [edge["claim_id"] for edge in body["edges"]]


def test_graph_predicate_filter_applies_at_depth_2(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    sample_edge_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_edge = {
        "claim_id": "CLM-9022",
        "subject_entity_id": "ENT-0003",
        "predicate": "appears_in",
        "object_entity_id": "ENT-0099",
        "evidence_status": "official_confirmed",
        "confidence": 0.8,
        "source_id": "SRC-GI-0001",
        "asset_id": None,
        "claim_status": "active",
    }

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)

    captured_calls: list[dict[str, Any]] = []

    def _fake_fetch_claim_edges(_c, **kwargs):
        captured_calls.append(kwargs)
        if kwargs["touching_entity_ids"] == {"ENT-0121"}:
            return [sample_edge_row]
        return [second_edge]

    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [
            sample_seed_row,
            sample_neighbor_row,
            {
                "entity_id": "ENT-0099",
                "canonical_name": "Teyvat",
                "entity_type": "world",
                "primary_scope_game": "Genshin Impact",
                "display_label": "Teyvat",
                "short_description": "The world of Genshin Impact.",
            },
        ],
    )

    response = client.get("/graph?seed_entity_id=ENT-0121&depth=2&predicate=appears_in")
    assert response.status_code == 200
    body = response.json()
    assert [edge["claim_id"] for edge in body["edges"]] == ["CLM-9021", "CLM-9022"]
    assert len(captured_calls) == 2
    assert all(call["predicate"] == "appears_in" for call in captured_calls)


def test_graph_confidence_min_filter_is_passed(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_fetch_claim_edges(_c, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)
    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    monkeypatch.setattr(graph, "_fetch_entities_by_ids", lambda _c, _ids: [sample_seed_row])

    response = client.get("/graph?seed_entity_id=ENT-0121&confidence_min=0.6")
    assert response.status_code == 200
    assert captured["confidence_min"] == 0.6


def test_graph_confidence_min_filter_applies_at_depth_1(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    sample_edge_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)

    def _fake_fetch_claim_edges(_c, **kwargs):
        assert kwargs["confidence_min"] == 0.6
        return [sample_edge_row]

    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [sample_seed_row, sample_neighbor_row],
    )

    response = client.get("/graph?seed_entity_id=ENT-0121&depth=1&confidence_min=0.6")
    assert response.status_code == 200
    body = response.json()
    assert [edge["claim_id"] for edge in body["edges"]] == ["CLM-9021"]


def test_graph_confidence_min_filter_applies_at_depth_2(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    sample_edge_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_edge = {
        "claim_id": "CLM-9022",
        "subject_entity_id": "ENT-0003",
        "predicate": "appears_in",
        "object_entity_id": "ENT-0099",
        "evidence_status": "official_confirmed",
        "confidence": 0.8,
        "source_id": "SRC-GI-0001",
        "asset_id": None,
        "claim_status": "active",
    }

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)

    captured_calls: list[dict[str, Any]] = []

    def _fake_fetch_claim_edges(_c, **kwargs):
        captured_calls.append(kwargs)
        if kwargs["touching_entity_ids"] == {"ENT-0121"}:
            return [sample_edge_row]
        return [second_edge]

    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [
            sample_seed_row,
            sample_neighbor_row,
            {
                "entity_id": "ENT-0099",
                "canonical_name": "Teyvat",
                "entity_type": "world",
                "primary_scope_game": "Genshin Impact",
                "display_label": "Teyvat",
                "short_description": "The world of Genshin Impact.",
            },
        ],
    )

    response = client.get("/graph?seed_entity_id=ENT-0121&depth=2&confidence_min=0.6")
    assert response.status_code == 200
    body = response.json()
    assert [edge["claim_id"] for edge in body["edges"]] == ["CLM-9021", "CLM-9022"]
    assert len(captured_calls) == 2
    assert all(call["confidence_min"] == 0.6 for call in captured_calls)


def test_graph_confidence_min_excludes_null_confidence(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)
    monkeypatch.setattr(graph, "_fetch_claim_edges", lambda _c, **_kwargs: [])
    monkeypatch.setattr(graph, "_fetch_entities_by_ids", lambda _c, _ids: [sample_seed_row])

    response = client.get("/graph?seed_entity_id=ENT-0121&confidence_min=0.6")
    assert response.status_code == 200
    body = response.json()
    assert [node["entity_id"] for node in body["nodes"]] == ["ENT-0121"]
    assert body["edges"] == []


def test_graph_evidence_status_filter_is_passed(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_fetch_claim_edges(_c, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)
    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    monkeypatch.setattr(graph, "_fetch_entities_by_ids", lambda _c, _ids: [sample_seed_row])

    response = client.get("/graph?seed_entity_id=ENT-0121&evidence_status=official_confirmed")
    assert response.status_code == 200
    assert captured["evidence_status"] == "official_confirmed"


def test_graph_evidence_status_filter_applies_at_depth_1(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    sample_edge_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)

    def _fake_fetch_claim_edges(_c, **kwargs):
        assert kwargs["evidence_status"] == "official_confirmed"
        return [sample_edge_row]

    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [sample_seed_row, sample_neighbor_row],
    )

    response = client.get(
        "/graph?seed_entity_id=ENT-0121&depth=1&evidence_status=official_confirmed"
    )
    assert response.status_code == 200
    body = response.json()
    assert [edge["claim_id"] for edge in body["edges"]] == ["CLM-9021"]


def test_graph_evidence_status_filter_applies_at_depth_2(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    sample_edge_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_edge = {
        "claim_id": "CLM-9022",
        "subject_entity_id": "ENT-0003",
        "predicate": "appears_in",
        "object_entity_id": "ENT-0099",
        "evidence_status": "official_confirmed",
        "confidence": 0.8,
        "source_id": "SRC-GI-0001",
        "asset_id": None,
        "claim_status": "active",
    }

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)

    captured_calls: list[dict[str, Any]] = []

    def _fake_fetch_claim_edges(_c, **kwargs):
        captured_calls.append(kwargs)
        if kwargs["touching_entity_ids"] == {"ENT-0121"}:
            return [sample_edge_row]
        return [second_edge]

    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [
            sample_seed_row,
            sample_neighbor_row,
            {
                "entity_id": "ENT-0099",
                "canonical_name": "Teyvat",
                "entity_type": "world",
                "primary_scope_game": "Genshin Impact",
                "display_label": "Teyvat",
                "short_description": "The world of Genshin Impact.",
            },
        ],
    )

    response = client.get(
        "/graph?seed_entity_id=ENT-0121&depth=2&evidence_status=official_confirmed"
    )
    assert response.status_code == 200
    body = response.json()
    assert [edge["claim_id"] for edge in body["edges"]] == ["CLM-9021", "CLM-9022"]
    assert len(captured_calls) == 2
    assert all(call["evidence_status"] == "official_confirmed" for call in captured_calls)


def test_graph_invalid_predicate_returns_422(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: ["invalid predicate"])
    response = client.get("/graph?seed_entity_id=ENT-0121&predicate=bad_pred")
    assert response.status_code == 422


def test_graph_blank_predicate_returns_422(client: TestClient) -> None:
    response = client.get("/graph?seed_entity_id=ENT-0121&predicate=   ")
    assert response.status_code == 422


def test_graph_blank_evidence_status_returns_422(client: TestClient) -> None:
    response = client.get("/graph?seed_entity_id=ENT-0121&evidence_status=   ")
    assert response.status_code == 422


def test_graph_valid_predicate_with_no_matching_edges_returns_seed_node_and_empty_edges(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)
    monkeypatch.setattr(graph, "_fetch_claim_edges", lambda _c, **_kwargs: [])
    monkeypatch.setattr(graph, "_fetch_entities_by_ids", lambda _c, _ids: [sample_seed_row])

    response = client.get("/graph?seed_entity_id=ENT-0121&predicate=appears_in")
    assert response.status_code == 200
    body = response.json()
    assert [node["entity_id"] for node in body["nodes"]] == ["ENT-0121"]
    assert body["edges"] == []


def test_graph_combined_filters_use_and_semantics(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    sample_edge_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)

    def _fake_fetch_claim_edges(_c, **kwargs):
        assert kwargs["predicate"] == "appears_in"
        assert kwargs["confidence_min"] == 0.6
        assert kwargs["evidence_status"] == "official_confirmed"
        return [sample_edge_row]

    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [sample_seed_row, sample_neighbor_row],
    )

    response = client.get(
        "/graph?seed_entity_id=ENT-0121&predicate=appears_in&confidence_min=0.6"
        "&evidence_status=official_confirmed"
    )
    assert response.status_code == 200
    body = response.json()
    assert [edge["claim_id"] for edge in body["edges"]] == ["CLM-9021"]


def test_graph_valid_combined_filters_with_no_matching_edges_return_seed_only(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)
    monkeypatch.setattr(graph, "_fetch_claim_edges", lambda _c, **_kwargs: [])
    monkeypatch.setattr(graph, "_fetch_entities_by_ids", lambda _c, _ids: [sample_seed_row])

    response = client.get(
        "/graph?seed_entity_id=ENT-0121&predicate=appears_in&confidence_min=0.95"
        "&evidence_status=editorial_inference"
    )
    assert response.status_code == 200
    body = response.json()
    assert [node["entity_id"] for node in body["nodes"]] == ["ENT-0121"]
    assert body["edges"] == []


def test_graph_combined_filters_preserve_claim_direction(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directed_edge = {
        "claim_id": "CLM-7777",
        "subject_entity_id": "ENT-0003",
        "predicate": "identity_variant",
        "object_entity_id": "ENT-0121",
        "evidence_status": "editorial_inference",
        "confidence": 0.7,
        "source_id": None,
        "asset_id": None,
        "claim_status": "active",
    }

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)
    monkeypatch.setattr(graph, "_fetch_claim_edges", lambda _c, **_kwargs: [directed_edge])
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [sample_seed_row, sample_neighbor_row],
    )

    response = client.get(
        "/graph?seed_entity_id=ENT-0121&predicate=identity_variant&confidence_min=0.6"
        "&evidence_status=editorial_inference"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["edges"][0]["source"] == "ENT-0003"
    assert body["edges"][0]["target"] == "ENT-0121"


def test_graph_predicate_filter_preserves_claim_direction(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directed_edge = {
        "claim_id": "CLM-7777",
        "subject_entity_id": "ENT-0003",
        "predicate": "identity_variant",
        "object_entity_id": "ENT-0121",
        "evidence_status": "official_confirmed",
        "confidence": 0.8,
        "source_id": None,
        "asset_id": None,
        "claim_status": "active",
    }

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)
    monkeypatch.setattr(graph, "_fetch_claim_edges", lambda _c, **_kwargs: [directed_edge])
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [sample_seed_row, sample_neighbor_row],
    )

    response = client.get("/graph?seed_entity_id=ENT-0121&predicate=identity_variant")
    assert response.status_code == 200
    body = response.json()
    assert body["edges"][0]["source"] == "ENT-0003"
    assert body["edges"][0]["target"] == "ENT-0121"


def test_graph_seed_node_included_when_no_edges_found(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)
    monkeypatch.setattr(graph, "_fetch_claim_edges", lambda _c, **_kwargs: [])
    monkeypatch.setattr(graph, "_fetch_entities_by_ids", lambda _c, _ids: [sample_seed_row])

    response = client.get("/graph?seed_entity_id=ENT-0121")
    assert response.status_code == 200
    body = response.json()
    assert [node["entity_id"] for node in body["nodes"]] == ["ENT-0121"]
    assert body["edges"] == []


def test_graph_filters_apply_to_depth_2_edges(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_calls: list[dict[str, Any]] = []

    def _fake_fetch_claim_edges(_c, **kwargs):
        captured_calls.append(kwargs)
        return []

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)
    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    monkeypatch.setattr(graph, "_fetch_entities_by_ids", lambda _c, _ids: [sample_seed_row])

    response = client.get(
        "/graph?seed_entity_id=ENT-0121&depth=2&predicate=appears_in&confidence_min=0.6"
        "&evidence_status=official_confirmed"
    )
    assert response.status_code == 200
    assert len(captured_calls) == 2
    for call in captured_calls:
        assert call["predicate"] == "appears_in"
        assert call["confidence_min"] == 0.6
        assert call["evidence_status"] == "official_confirmed"


def test_graph_duplicate_nodes_are_deduped(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    sample_edge_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate_neighbor = dict(sample_neighbor_row)

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)
    monkeypatch.setattr(graph, "_fetch_claim_edges", lambda _c, **_kwargs: [sample_edge_row])
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [sample_seed_row, sample_neighbor_row, duplicate_neighbor],
    )

    response = client.get("/graph?seed_entity_id=ENT-0121")
    assert response.status_code == 200
    body = response.json()
    assert [node["entity_id"] for node in body["nodes"]] == ["ENT-0003", "ENT-0121"]


def test_graph_duplicate_claims_are_deduped(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    sample_edge_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate_edge = dict(sample_edge_row)

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)

    def _fake_fetch_claim_edges(_c, **kwargs):
        if kwargs["touching_entity_ids"] == {"ENT-0121"}:
            return [sample_edge_row]
        return [duplicate_edge]

    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [sample_seed_row, sample_neighbor_row],
    )

    response = client.get("/graph?seed_entity_id=ENT-0121&depth=2")
    assert response.status_code == 200
    body = response.json()
    assert [edge["claim_id"] for edge in body["edges"]] == ["CLM-9021"]


def test_graph_edge_limit_truncates_edges_deterministically(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edge_b = {
        "claim_id": "CLM-0002",
        "subject_entity_id": "ENT-0121",
        "predicate": "member_of",
        "object_entity_id": "ENT-0003",
        "evidence_status": "official_confirmed",
        "confidence": 0.7,
        "source_id": None,
        "asset_id": None,
        "claim_status": "active",
    }
    edge_a = {
        "claim_id": "CLM-0001",
        "subject_entity_id": "ENT-0003",
        "predicate": "part_of",
        "object_entity_id": "ENT-0099",
        "evidence_status": "official_confirmed",
        "confidence": 0.8,
        "source_id": None,
        "asset_id": None,
        "claim_status": "active",
    }

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)

    def _fake_fetch_claim_edges(_c, **kwargs):
        if kwargs["touching_entity_ids"] == {"ENT-0121"}:
            return [edge_b]
        return [edge_a]

    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)
    def _fake_fetch_entities_by_ids(_c, entity_ids):
        assert set(entity_ids) == {"ENT-0121", "ENT-0003", "ENT-0099"}
        return [
            sample_seed_row,
            {
                "entity_id": "ENT-0003",
                "canonical_name": "Inazuma",
                "entity_type": "location",
                "primary_scope_game": "Genshin Impact",
                "display_label": "Inazuma",
                "short_description": "Nation of eternity.",
            },
            {
                "entity_id": "ENT-0099",
                "canonical_name": "Teyvat",
                "entity_type": "world",
                "primary_scope_game": "Genshin Impact",
                "display_label": "Teyvat",
                "short_description": "The world of Genshin Impact.",
            },
        ]

    monkeypatch.setattr(graph, "_fetch_entities_by_ids", _fake_fetch_entities_by_ids)

    response = client.get("/graph?seed_entity_id=ENT-0121&depth=2&limit=1")
    assert response.status_code == 200
    body = response.json()
    assert [edge["claim_id"] for edge in body["edges"]] == ["CLM-0001"]
    assert [node["entity_id"] for node in body["nodes"]] == ["ENT-0003", "ENT-0099", "ENT-0121"]


def test_graph_predicate_filter_works_with_existing_depth_and_limit_behavior(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    depth_1_edge = {
        "claim_id": "CLM-0002",
        "subject_entity_id": "ENT-0121",
        "predicate": "appears_in",
        "object_entity_id": "ENT-0003",
        "evidence_status": "official_confirmed",
        "confidence": 0.9,
        "source_id": None,
        "asset_id": None,
        "claim_status": "active",
    }
    depth_2_edge = {
        "claim_id": "CLM-0001",
        "subject_entity_id": "ENT-0003",
        "predicate": "appears_in",
        "object_entity_id": "ENT-0099",
        "evidence_status": "official_confirmed",
        "confidence": 0.8,
        "source_id": None,
        "asset_id": None,
        "claim_status": "active",
    }

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)

    captured_calls: list[dict[str, Any]] = []

    def _fake_fetch_claim_edges(_c, **kwargs):
        captured_calls.append(kwargs)
        if kwargs["touching_entity_ids"] == {"ENT-0121"}:
            return [depth_1_edge]
        return [depth_2_edge]

    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)

    def _fake_fetch_entities_by_ids(_c, entity_ids):
        assert set(entity_ids) == {"ENT-0121", "ENT-0003", "ENT-0099"}
        return [
            sample_seed_row,
            {
                "entity_id": "ENT-0003",
                "canonical_name": "Inazuma",
                "entity_type": "location",
                "primary_scope_game": "Genshin Impact",
                "display_label": "Inazuma",
                "short_description": "Nation of eternity.",
            },
            {
                "entity_id": "ENT-0099",
                "canonical_name": "Teyvat",
                "entity_type": "world",
                "primary_scope_game": "Genshin Impact",
                "display_label": "Teyvat",
                "short_description": "The world of Genshin Impact.",
            },
        ]

    monkeypatch.setattr(graph, "_fetch_entities_by_ids", _fake_fetch_entities_by_ids)

    response = client.get("/graph?seed_entity_id=ENT-0121&depth=2&predicate=appears_in&limit=1")
    assert response.status_code == 200
    body = response.json()
    assert [edge["claim_id"] for edge in body["edges"]] == ["CLM-0001"]
    assert [node["entity_id"] for node in body["nodes"]] == ["ENT-0003", "ENT-0099", "ENT-0121"]
    assert len(captured_calls) == 2
    assert all(call["predicate"] == "appears_in" for call in captured_calls)


def test_graph_combined_filters_work_with_limit(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    depth_1_edge = {
        "claim_id": "CLM-0002",
        "subject_entity_id": "ENT-0121",
        "predicate": "identity_variant",
        "object_entity_id": "ENT-0003",
        "evidence_status": "editorial_inference",
        "confidence": 0.7,
        "source_id": None,
        "asset_id": None,
        "claim_status": "active",
    }
    depth_2_edge = {
        "claim_id": "CLM-0001",
        "subject_entity_id": "ENT-0003",
        "predicate": "identity_variant",
        "object_entity_id": "ENT-0099",
        "evidence_status": "editorial_inference",
        "confidence": 0.8,
        "source_id": None,
        "asset_id": None,
        "claim_status": "active",
    }

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)

    captured_calls: list[dict[str, Any]] = []

    def _fake_fetch_claim_edges(_c, **kwargs):
        captured_calls.append(kwargs)
        if kwargs["touching_entity_ids"] == {"ENT-0121"}:
            return [depth_1_edge]
        return [depth_2_edge]

    monkeypatch.setattr(graph, "_fetch_claim_edges", _fake_fetch_claim_edges)

    def _fake_fetch_entities_by_ids(_c, entity_ids):
        assert set(entity_ids) == {"ENT-0121", "ENT-0003", "ENT-0099"}
        return [
            sample_seed_row,
            {
                "entity_id": "ENT-0003",
                "canonical_name": "Kiana Kaslana",
                "entity_type": "character",
                "primary_scope_game": "Honkai Impact 3",
                "display_label": "Kiana Kaslana",
                "short_description": "A direct neighbor.",
            },
            {
                "entity_id": "ENT-0099",
                "canonical_name": "Herrscher Form",
                "entity_type": "concept",
                "primary_scope_game": "Honkai Impact 3",
                "display_label": "Herrscher Form",
                "short_description": "A second-hop concept.",
            },
        ]

    monkeypatch.setattr(graph, "_fetch_entities_by_ids", _fake_fetch_entities_by_ids)

    response = client.get(
        "/graph?seed_entity_id=ENT-0121&depth=2&predicate=identity_variant"
        "&confidence_min=0.6&evidence_status=editorial_inference&limit=1"
    )
    assert response.status_code == 200
    body = response.json()
    assert [edge["claim_id"] for edge in body["edges"]] == ["CLM-0001"]
    assert [node["entity_id"] for node in body["nodes"]] == ["ENT-0003", "ENT-0099", "ENT-0121"]
    assert len(captured_calls) == 2
    for call in captured_calls:
        assert call["predicate"] == "identity_variant"
        assert call["confidence_min"] == 0.6
        assert call["evidence_status"] == "editorial_inference"


def test_graph_nodes_only_include_seed_and_nodes_needed_by_returned_edges(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edge = {
        "claim_id": "CLM-0001",
        "subject_entity_id": "ENT-0121",
        "predicate": "appears_in",
        "object_entity_id": "ENT-0003",
        "evidence_status": "official_confirmed",
        "confidence": 0.9,
        "source_id": None,
        "asset_id": None,
        "claim_status": "active",
    }

    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)
    monkeypatch.setattr(graph, "_fetch_claim_edges", lambda _c, **_kwargs: [edge])

    captured_entity_ids: list[set[str]] = []

    def _fake_fetch_entities_by_ids(_c, entity_ids):
        captured_entity_ids.append(set(entity_ids))
        return [
            sample_seed_row,
            {
                "entity_id": "ENT-0003",
                "canonical_name": "Inazuma",
                "entity_type": "location",
                "primary_scope_game": "Genshin Impact",
                "display_label": "Inazuma",
                "short_description": "Nation of eternity.",
            },
        ]

    monkeypatch.setattr(graph, "_fetch_entities_by_ids", _fake_fetch_entities_by_ids)

    response = client.get("/graph?seed_entity_id=ENT-0121&limit=1")
    assert response.status_code == 200
    assert captured_entity_ids == [{"ENT-0121", "ENT-0003"}]


def test_graph_response_shape_has_nodes_and_edges(
    client: TestClient,
    sample_seed_row: dict[str, Any],
    sample_neighbor_row: dict[str, Any],
    sample_edge_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(graph, "validate_predicate_usage", lambda _predicate: [])
    monkeypatch.setattr(graph, "_fetch_entity_by_id", lambda _c, _id: sample_seed_row)
    monkeypatch.setattr(graph, "_fetch_claim_edges", lambda _c, **_kwargs: [sample_edge_row])
    monkeypatch.setattr(
        graph,
        "_fetch_entities_by_ids",
        lambda _c, _ids: [sample_seed_row, sample_neighbor_row],
    )

    response = client.get("/graph?seed_entity_id=ENT-0121")
    assert response.status_code == 200
    body = response.json()
    assert "nodes" in body
    assert "edges" in body
    assert body["nodes"][0]["id"] == body["nodes"][0]["entity_id"]
    assert body["edges"][0]["id"] == body["edges"][0]["claim_id"]
