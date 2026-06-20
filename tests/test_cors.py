"""Regression tests for frontend-to-backend CORS behavior."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def test_health_get_allows_local_frontend_origin() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_preflight_options_allows_local_frontend_origin() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/search",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
    assert "GET" in response.headers["access-control-allow-methods"]
