"""Shared graph response models."""

from __future__ import annotations

from pydantic import BaseModel


class GraphNode(BaseModel):
    """Frontend-ready graph node payload."""

    id: str
    entity_id: str
    label: str
    canonical_name: str
    entity_type: str
    primary_scope_game: str | None = None
    short_description: str | None = None


class GraphEdge(BaseModel):
    """Frontend-ready directed edge payload derived from claims."""

    id: str
    claim_id: str
    source: str
    target: str
    predicate: str
    confidence: float | None = None
    evidence_status: str | None = None
    source_id: str | None = None
    asset_id: str | None = None
    claim_status: str | None = None


class GraphResponse(BaseModel):
    """Seed-centered graph response."""

    seed_entity_id: str
    depth: int
    nodes: list[GraphNode]
    edges: list[GraphEdge]
