"""Pure unit tests for graph row transformation helpers."""

from __future__ import annotations

from api.graph_transform import (
    row_to_graph_edge,
    row_to_graph_node,
    transform_claim_rows_to_edges,
    transform_entity_rows_to_nodes,
)


def test_entity_row_becomes_graph_node() -> None:
    row = {
        "entity_id": "ENT-0121",
        "canonical_name": "Raiden Shogun",
        "entity_type": "character",
        "primary_scope_game": "Genshin Impact",
        "display_label": "Raiden Shogun",
        "short_description": "Electro Archon of Inazuma.",
    }

    node = row_to_graph_node(row)
    assert node.id == "ENT-0121"
    assert node.entity_id == "ENT-0121"
    assert node.label == "Raiden Shogun"
    assert node.canonical_name == "Raiden Shogun"
    assert node.entity_type == "character"
    assert node.primary_scope_game == "Genshin Impact"
    assert node.short_description == "Electro Archon of Inazuma."


def test_claim_row_becomes_graph_edge() -> None:
    row = {
        "claim_id": "CLM-9021",
        "subject_entity_id": "ENT-0121",
        "predicate": "appears_in",
        "object_entity_id": "ENT-0003",
        "evidence_status": "official_confirmed",
        "confidence": 0.9,
        "source_id": "SRC-GI-0001",
        "asset_id": "AST-GI-0001",
        "claim_status": "active",
    }

    edge = row_to_graph_edge(row)
    assert edge.id == "CLM-9021"
    assert edge.claim_id == "CLM-9021"
    assert edge.source == "ENT-0121"
    assert edge.target == "ENT-0003"
    assert edge.predicate == "appears_in"
    assert edge.confidence == 0.9
    assert edge.evidence_status == "official_confirmed"
    assert edge.source_id == "SRC-GI-0001"
    assert edge.asset_id == "AST-GI-0001"
    assert edge.claim_status == "active"


def test_display_label_falls_back_to_canonical_name() -> None:
    row = {
        "entity_id": "ENT-0804",
        "canonical_name": "Kiana Kaslana",
        "entity_type": "character",
        "primary_scope_game": "Multi",
        "display_label": None,
        "short_description": "Core protagonist identity.",
    }

    node = row_to_graph_node(row)
    assert node.label == "Kiana Kaslana"


def test_duplicate_entities_are_deduped() -> None:
    first = {
        "entity_id": "ENT-0003",
        "canonical_name": "Inazuma",
        "entity_type": "location",
        "primary_scope_game": "Genshin Impact",
        "display_label": "Inazuma",
        "short_description": "Nation of eternity.",
    }
    duplicate = dict(first)

    nodes = transform_entity_rows_to_nodes([first, duplicate])
    assert len(nodes) == 1
    assert nodes[0].entity_id == "ENT-0003"


def test_duplicate_claims_are_deduped() -> None:
    first = {
        "claim_id": "CLM-9021",
        "subject_entity_id": "ENT-0121",
        "predicate": "appears_in",
        "object_entity_id": "ENT-0003",
        "evidence_status": "official_confirmed",
        "confidence": 0.9,
        "source_id": "SRC-GI-0001",
        "asset_id": "AST-GI-0001",
        "claim_status": "active",
    }
    duplicate = dict(first)

    edges = transform_claim_rows_to_edges([first, duplicate])
    assert len(edges) == 1
    assert edges[0].claim_id == "CLM-9021"


def test_edge_direction_is_subject_to_object() -> None:
    row = {
        "claim_id": "CLM-1000",
        "subject_entity_id": "ENT-0001",
        "predicate": "member_of",
        "object_entity_id": "ENT-0002",
        "evidence_status": None,
        "confidence": None,
        "source_id": None,
        "asset_id": None,
        "claim_status": None,
    }

    edge = row_to_graph_edge(row)
    assert edge.source == "ENT-0001"
    assert edge.target == "ENT-0002"


def test_nodes_sorted_by_entity_id() -> None:
    rows = [
        {
            "entity_id": "ENT-0100",
            "canonical_name": "B",
            "entity_type": "character",
            "primary_scope_game": None,
            "display_label": None,
            "short_description": None,
        },
        {
            "entity_id": "ENT-0002",
            "canonical_name": "A",
            "entity_type": "character",
            "primary_scope_game": None,
            "display_label": None,
            "short_description": None,
        },
    ]

    nodes = transform_entity_rows_to_nodes(rows)
    assert [node.entity_id for node in nodes] == ["ENT-0002", "ENT-0100"]


def test_edges_sorted_by_claim_id() -> None:
    rows = [
        {
            "claim_id": "CLM-0900",
            "subject_entity_id": "ENT-0001",
            "predicate": "appears_in",
            "object_entity_id": "ENT-0002",
            "evidence_status": None,
            "confidence": None,
            "source_id": None,
            "asset_id": None,
            "claim_status": None,
        },
        {
            "claim_id": "CLM-0001",
            "subject_entity_id": "ENT-0002",
            "predicate": "part_of",
            "object_entity_id": "ENT-0003",
            "evidence_status": None,
            "confidence": None,
            "source_id": None,
            "asset_id": None,
            "claim_status": None,
        },
    ]

    edges = transform_claim_rows_to_edges(rows)
    assert [edge.claim_id for edge in edges] == ["CLM-0001", "CLM-0900"]
