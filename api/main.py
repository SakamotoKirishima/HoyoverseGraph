"""FastAPI app entrypoint for HoYoverse Knowledge Graph backend APIs.

Run:
    uvicorn api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.claims import router as claims_router
from api.entities import router as entities_router
from api.search import router as search_router
from api.source_assets import router as source_assets_router
from api.sources import router as sources_router

app = FastAPI(
    title="HoYoverse Knowledge Graph API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    # Keep local frontend development friction-free without widening origins beyond
    # the common Next.js dev hosts we use in this repo.
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health endpoint."""
    return {"status": "ok"}


app.include_router(entities_router)
app.include_router(claims_router)
app.include_router(search_router)
app.include_router(sources_router)
app.include_router(source_assets_router)
