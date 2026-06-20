"""FastAPI app entrypoint for HoYoverse Knowledge Graph backend APIs.

Run:
    uvicorn api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.claims import router as claims_router
from api.graph import router as graph_router
from api.entities import router as entities_router
from api.search import router as search_router
from api.source_assets import router as source_assets_router
from api.sources import router as sources_router

app = FastAPI(
    title="HoYoverse Knowledge Graph API",
    version="0.1.0",
)

# Allow the local Next.js frontend to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health endpoint."""
    return {"status": "ok"}


app.include_router(entities_router)
app.include_router(claims_router)
app.include_router(graph_router)
app.include_router(sources_router)
app.include_router(source_assets_router)
