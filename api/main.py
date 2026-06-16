"""FastAPI app entrypoint for HoYoverse Knowledge Graph backend APIs.

Run:
    uvicorn api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from api.claims import router as claims_router
from api.entities import router as entities_router
from api.source_assets import router as source_assets_router
from api.sources import router as sources_router

app = FastAPI(
    title="HoYoverse Knowledge Graph API",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health endpoint."""
    return {"status": "ok"}


app.include_router(entities_router)
app.include_router(claims_router)
app.include_router(sources_router)
app.include_router(source_assets_router)
