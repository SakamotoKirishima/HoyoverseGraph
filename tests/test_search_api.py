"""API tests for search endpoint behavior using TestClient + monkeypatch seams."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api import search
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

    app.dependency_overrides[search.get_db_connection] = _override_get_db_connection
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def sample_search_row() -> dict[str, Any]:
    return {
        "entity_id": "ENT-0121",
        "canonical_name": "Raiden Shogun",
        "display_label": "Raiden Shogun",
        "entity_type": "character",
        "primary_scope_game": "Genshin Impact",
        "aliases_pipe_delimited": "Ei|Raiden Ei",
        "short_description": "Electro Archon of Inazuma.",
        "source_count": 4,
    }


def test_search_success_returns_expected_shape(
    client: TestClient,
    sample_search_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(search, "_search_entities", lambda _c, **_kwargs: [sample_search_row])
    response = client.get("/search?q=raiden")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["entity_id"] == "ENT-0121"
    assert body[0]["aliases"] == ["Ei", "Raiden Ei"]
    assert body[0]["source_count"] == 4
    assert "aliases_pipe_delimited" not in body[0]


def test_search_blank_q_returns_422(client: TestClient) -> None:
    response = client.get("/search?q=   ")
    assert response.status_code == 422
    assert response.json()["detail"] == ["q cannot be blank."]


def test_search_invalid_entity_type_returns_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(search, "get_allowed_entity_types", lambda: {"character"})
    response = client.get("/search?q=bronya&entity_type=not_a_type")
    assert response.status_code == 422


def test_search_blank_entity_type_returns_422(client: TestClient) -> None:
    response = client.get("/search?q=bronya&entity_type=   ")
    assert response.status_code == 422


def test_search_invalid_primary_scope_game_returns_422(client: TestClient) -> None:
    response = client.get("/search?q=raiden&primary_scope_game=NotAGame")
    assert response.status_code == 422


def test_search_blank_primary_scope_game_returns_422(client: TestClient) -> None:
    response = client.get("/search?q=raiden&primary_scope_game=   ")
    assert response.status_code == 422


def test_search_limit_and_offset_validation(client: TestClient) -> None:
    assert client.get("/search?q=welt&limit=0").status_code == 422
    assert client.get("/search?q=welt&limit=101").status_code == 422
    assert client.get("/search?q=welt&offset=-1").status_code == 422


def test_search_entity_type_filter_is_passed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_search(_c, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(search, "get_allowed_entity_types", lambda: {"character"})
    monkeypatch.setattr(search, "_search_entities", _fake_search)

    response = client.get("/search?q=bronya&entity_type=character")
    assert response.status_code == 200
    assert captured["entity_type"] == "character"
    assert captured["primary_scope_game"] is None


def test_search_primary_scope_game_canonical_filter_is_passed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_search(_c, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(search, "_search_entities", _fake_search)

    response = client.get("/search?q=bronya&primary_scope_game=Honkai:%20Star%20Rail")
    assert response.status_code == 200
    assert captured["entity_type"] is None
    assert captured["primary_scope_game"] == "Honkai: Star Rail"


def test_search_primary_scope_game_alias_filter_is_normalized(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_search(_c, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(search, "_search_entities", _fake_search)

    response = client.get("/search?q=bronya&primary_scope_game=HSR")
    assert response.status_code == 200
    assert captured["primary_scope_game"] == "Honkai: Star Rail"


def test_search_entity_type_and_game_filters_are_passed_together(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_search(_c, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(search, "get_allowed_entity_types", lambda: {"character"})
    monkeypatch.setattr(search, "_search_entities", _fake_search)

    response = client.get(
        "/search?q=raiden&entity_type=character&primary_scope_game=Genshin&limit=50&offset=100"
    )
    assert response.status_code == 200
    assert captured["q"] == "raiden"
    assert captured["entity_type"] == "character"
    assert captured["primary_scope_game"] == "Genshin Impact"
    assert captured["limit"] == 50
    assert captured["offset"] == 100


def test_search_response_handles_missing_sources(
    client: TestClient,
    sample_search_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = dict(sample_search_row)
    row["aliases_pipe_delimited"] = None
    row["source_count"] = 0
    monkeypatch.setattr(search, "_search_entities", lambda _c, **_kwargs: [row])
    response = client.get("/search?q=kaslana")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["aliases"] == []
    assert body[0]["source_count"] == 0


def test_search_omitted_filters_leave_search_unfiltered(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_search(_c, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(search, "_search_entities", _fake_search)

    response = client.get("/search?q=kaslana&limit=10&offset=5")
    assert response.status_code == 200
    assert captured["entity_type"] is None
    assert captured["primary_scope_game"] is None
    assert captured["limit"] == 10
    assert captured["offset"] == 5


def test_search_exact_alias_match_is_case_insensitive(
    client: TestClient,
    sample_search_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = dict(sample_search_row)
    row["canonical_name"] = "Beelzebul"
    row["display_label"] = "Shogun"
    row["aliases_pipe_delimited"] = "Ei|Raiden Ei"
    monkeypatch.setattr(search, "_search_entities", lambda _c, **_kwargs: [row])
    response = client.get("/search?q=ei")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["aliases"] == ["Ei", "Raiden Ei"]


def test_search_prefix_alias_match_returns_result(
    client: TestClient,
    sample_search_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = dict(sample_search_row)
    row["aliases_pipe_delimited"] = "Ei|Raiden Ei|Electro Archon"
    monkeypatch.setattr(search, "_search_entities", lambda _c, **_kwargs: [row])
    response = client.get("/search?q=Electro")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["aliases"] == ["Ei", "Raiden Ei", "Electro Archon"]


def test_search_exact_canonical_match_outranks_alias_match(
    client: TestClient,
    sample_search_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_row = dict(sample_search_row)
    canonical_row["entity_id"] = "ENT-0001"
    canonical_row["canonical_name"] = "Ei"
    canonical_row["display_label"] = "Ei"
    canonical_row["aliases_pipe_delimited"] = None

    alias_row = dict(sample_search_row)
    alias_row["entity_id"] = "ENT-0002"
    alias_row["canonical_name"] = "Raiden Shogun"
    alias_row["display_label"] = "Raiden Shogun"
    alias_row["aliases_pipe_delimited"] = "Ei|Raiden Ei"

    monkeypatch.setattr(
        search,
        "_search_entities",
        lambda _c, **_kwargs: [alias_row, canonical_row],
    )
    response = client.get("/search?q=Ei")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["entity_id"] == "ENT-0001"
    assert body[1]["entity_id"] == "ENT-0002"


def test_search_exact_alias_match_outranks_description_only_match(
    client: TestClient,
    sample_search_row: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alias_row = dict(sample_search_row)
    alias_row["entity_id"] = "ENT-0001"
    alias_row["aliases_pipe_delimited"] = "Ei|Raiden Ei"
    alias_row["short_description"] = "Electro Archon of Inazuma."

    description_row = dict(sample_search_row)
    description_row["entity_id"] = "ENT-0002"
    description_row["canonical_name"] = "Inazuma Ruler"
    description_row["display_label"] = "Inazuma Ruler"
    description_row["aliases_pipe_delimited"] = None
    description_row["short_description"] = "Known to some as Raiden Ei."

    monkeypatch.setattr(
        search,
        "_search_entities",
        lambda _c, **_kwargs: [description_row, alias_row],
    )
    response = client.get("/search?q=Raiden%20Ei")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["entity_id"] == "ENT-0001"
    assert body[1]["entity_id"] == "ENT-0002"


def test_search_filters_still_work_with_alias_queries(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_search(_c, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(search, "get_allowed_entity_types", lambda: {"character"})
    monkeypatch.setattr(search, "_search_entities", _fake_search)
    response = client.get(
        "/search?q=Ei&entity_type=character&primary_scope_game=Genshin Impact"
    )
    assert response.status_code == 200
    assert captured["q"] == "Ei"
    assert captured["entity_type"] == "character"
    assert captured["primary_scope_game"] == "Genshin Impact"
