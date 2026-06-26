"""API tests for deployment health endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api import main
from api.main import app


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_health_returns_process_liveness_shape(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "hoyoverse-graph-api",
    }


def test_health_db_returns_ok_when_database_is_reachable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "ping_database", lambda: True)

    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "hoyoverse-graph-api",
        "database": "ok",
    }


def test_health_db_returns_503_when_database_is_unavailable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "ping_database", lambda: False)

    response = client.get("/health/db")

    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "service": "hoyoverse-graph-api",
        "database": "unavailable",
    }
