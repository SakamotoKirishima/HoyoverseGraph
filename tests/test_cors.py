"""Regression tests for frontend-to-backend CORS behavior."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api import config
from api.main import app, create_app


def test_default_local_origins_used_when_env_var_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

    assert config.get_allowed_origins() == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_comma_separated_origins_parse_correctly() -> None:
    parsed = config.parse_allowed_origins("https://a.example,https://b.example")

    assert parsed == ["https://a.example", "https://b.example"]


def test_whitespace_is_trimmed_and_empty_entries_ignored() -> None:
    parsed = config.parse_allowed_origins(
        " https://a.example , , http://localhost:3000  ,,"
    )

    assert parsed == ["https://a.example", "http://localhost:3000"]


def test_cors_middleware_uses_configured_origins() -> None:
    custom_app = create_app(allowed_origins=["https://frontend.example.com"])

    with TestClient(custom_app) as client:
        allowed_response = client.get(
            "/health",
            headers={"Origin": "https://frontend.example.com"},
        )
        blocked_response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )

    assert allowed_response.status_code == 200
    assert (
        allowed_response.headers["access-control-allow-origin"]
        == "https://frontend.example.com"
    )
    assert "access-control-allow-origin" not in blocked_response.headers


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
