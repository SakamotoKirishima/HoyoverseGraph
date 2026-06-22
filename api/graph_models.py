"""Shared graph response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """Frontend-ready graph node payload."""

    id: str = Field(description="Stable graph node identifier. Matches entity_id.")
    entity_id: str = Field(description="Entity identifier in ENT-#### format.")
    label: str = Field(
        description="Display label for the node. Uses display_label when available, otherwise canonical_name."
    )
    canonical_name: str = Field(description="Canonical entity name.")
    entity_type: str = Field(description="Ontology entity type code for styling and filtering.")
    primary_scope_game: str | None = Field(
        default=None,
        description="Canonical primary scope game when available.",
    )
    short_description: str | None = Field(
        default=None,
        description="Short descriptive text shown in graph UI summaries when available.",
    )


class GraphEdge(BaseModel):
    """Frontend-ready directed edge payload derived from claims."""

    id: str = Field(description="Stable graph edge identifier. Matches claim_id.")
    claim_id: str = Field(description="Claim identifier in CLM-#### format.")
    source: str = Field(
        description="Source node entity_id. Preserves claim direction from subject_entity_id."
    )
    target: str = Field(
        description="Target node entity_id. Preserves claim direction to object_entity_id."
    )
    predicate: str = Field(description="Exact claim predicate code.")
    confidence: float | None = Field(
        default=None,
        description="Optional claim confidence between 0 and 1.",
    )
    evidence_status: str | None = Field(
        default=None,
        description="Optional evidence strength or provenance status for the claim.",
    )
    source_id: str | None = Field(
        default=None,
        description="Optional linked source record identifier.",
    )
    asset_id: str | None = Field(
        default=None,
        description="Optional linked source asset identifier.",
    )
    claim_status: str | None = Field(
        default=None,
        description="Optional claim lifecycle status such as active or draft.",
    )


class GraphResponse(BaseModel):
    """Seed-centered graph response."""

    seed_entity_id: str = Field(description="Seed entity identifier used to build the graph.")
    depth: int = Field(description="Expansion depth used for this graph response.")
    nodes: list[GraphNode] = Field(description="Entity nodes included in the graph neighborhood.")
    edges: list[GraphEdge] = Field(description="Directed claim edges included in the graph neighborhood.")
