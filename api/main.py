"""FastAPI app entrypoint for HoYoverse Knowledge Graph backend APIs.

Run:
    uvicorn api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.claims import router as claims_router
from api.config import get_allowed_origins
from api.db import ping_database
from api.graph import router as graph_router
from api.entities import router as entities_router
from api.search import router as search_router
from api.source_assets import router as source_assets_router
from api.sources import router as sources_router


def create_app(*, allowed_origins: list[str] | None = None) -> FastAPI:
    """Create the FastAPI app with environment-aware CORS configuration."""
    app = FastAPI(
        title="HoYoverse Knowledge Graph API",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins if allowed_origins is not None else get_allowed_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Simple health endpoint."""
        return {"status": "ok", "service": "hoyoverse-graph-api"}

    @app.get("/health/db")
    def health_db() -> JSONResponse:
        """Database-backed health endpoint for deployment readiness checks."""
        if ping_database():
            return JSONResponse(
                status_code=200,
                content={
                    "status": "ok",
                    "service": "hoyoverse-graph-api",
                    "database": "ok",
                },
            )

        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "service": "hoyoverse-graph-api",
                "database": "unavailable",
            },
        )

    app.include_router(entities_router)
    app.include_router(claims_router)
    app.include_router(graph_router)
    app.include_router(search_router)
    app.include_router(sources_router)
    app.include_router(source_assets_router)
    return app


app = create_app()
