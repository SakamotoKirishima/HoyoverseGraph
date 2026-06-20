"""Pure graph transformation helpers.

This module converts raw entity and claim rows into stable graph response
objects, independent from database fetching.
"""

from __future__ import annotations

from typing import Any

from api.graph_models import GraphEdge, GraphNode


def row_to_graph_node(row: dict[str, Any]) -> GraphNode:
    """Convert one raw entity row into a graph node."""
    label = row.get("display_label") or row["canonical_name"]
    return GraphNode(
        id=row["entity_id"],
        entity_id=row["entity_id"],
        label=label,
        canonical_name=row["canonical_name"],
        entity_type=row["entity_type"],
        primary_scope_game=row.get("primary_scope_game"),
        short_description=row.get("short_description"),
    )


def row_to_graph_edge(row: dict[str, Any]) -> GraphEdge:
    """Convert one raw claim row into a directed graph edge."""
    return GraphEdge(
        id=row["claim_id"],
        claim_id=row["claim_id"],
        source=row["subject_entity_id"],
        target=row["object_entity_id"],
        predicate=row["predicate"],
        confidence=row.get("confidence"),
        evidence_status=row.get("evidence_status"),
        source_id=row.get("source_id"),
        asset_id=row.get("asset_id"),
        claim_status=row.get("claim_status"),
    )


def transform_entity_rows_to_nodes(rows: list[dict[str, Any]]) -> list[GraphNode]:
    """Transform raw entity rows into deduped, sorted graph nodes."""
    deduped_nodes: dict[str, GraphNode] = {}
    for row in rows:
        node = row_to_graph_node(row)
        deduped_nodes[node.entity_id] = node
    return sorted(deduped_nodes.values(), key=lambda node: node.entity_id)


def transform_claim_rows_to_edges(rows: list[dict[str, Any]]) -> list[GraphEdge]:
    """Transform raw claim rows into deduped, sorted graph edges."""
    deduped_edges: dict[str, GraphEdge] = {}
    for row in rows:
        edge = row_to_graph_edge(row)
        deduped_edges[edge.claim_id] = edge
    return sorted(deduped_edges.values(), key=lambda edge: edge.claim_id)
