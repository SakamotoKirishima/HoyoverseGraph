"""Graph endpoint for seed-based entity/claim neighborhood traversal.

Current scope:
- Expand from a seed entity across claims as directed edges.
- Return entity nodes plus claim edges for depth 1 or 2.
- Support lightweight filtering by predicate, confidence, and evidence_status.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import Connection

from api.claim_validation import PredicateCatalogUnavailableError, validate_predicate_usage
from api.db import get_db_connection
from api.graph_models import GraphResponse
from api.graph_transform import transform_claim_rows_to_edges, transform_entity_rows_to_nodes

router = APIRouter(tags=["graph"])

ENT_ID_PATTERN = re.compile(r"^ENT-\d{4}$")


def _trim_or_none(value: str | None) -> str | None:
    """Trim whitespace and convert blanks to None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _fetch_entity_by_id(conn: Connection[Any], entity_id: str) -> dict[str, Any] | None:
    """Fetch one entity row needed for graph nodes."""
    sql = """
        SELECT
            entity_id,
            canonical_name,
            entity_type,
            primary_scope_game,
            display_label,
            short_description
        FROM entities
        WHERE entity_id = %(entity_id)s
        LIMIT 1;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"entity_id": entity_id})
        return cur.fetchone()


def _fetch_entities_by_ids(conn: Connection[Any], entity_ids: set[str]) -> list[dict[str, Any]]:
    """Fetch unique entity rows for a graph node set."""
    if not entity_ids:
        return []

    sql = """
        SELECT
            entity_id,
            canonical_name,
            entity_type,
            primary_scope_game,
            display_label,
            short_description
        FROM entities
        WHERE entity_id = ANY(%(entity_ids)s)
        ORDER BY entity_id ASC;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"entity_ids": list(entity_ids)})
        rows = cur.fetchall()
    return rows if rows is not None else []


def _fetch_claim_edges(
    conn: Connection[Any],
    *,
    touching_entity_ids: set[str],
    predicate: str | None,
    confidence_min: float | None,
    evidence_status: str | None,
) -> list[dict[str, Any]]:
    """Fetch claims touching a set of entities with stable ordering."""
    if not touching_entity_ids:
        return []

    where_clauses = [
        "(subject_entity_id = ANY(%(touching_entity_ids)s) OR object_entity_id = ANY(%(touching_entity_ids)s))"
    ]
    params: dict[str, Any] = {
        "touching_entity_ids": list(touching_entity_ids),
    }

    if predicate is not None:
        where_clauses.append("predicate = %(predicate)s")
        params["predicate"] = predicate

    if confidence_min is not None:
        where_clauses.append("confidence >= %(confidence_min)s")
        params["confidence_min"] = confidence_min

    if evidence_status is not None:
        where_clauses.append("evidence_status = %(evidence_status)s")
        params["evidence_status"] = evidence_status

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT
            claim_id,
            subject_entity_id,
            predicate,
            object_entity_id,
            evidence_status,
            confidence,
            source_id,
            asset_id,
            claim_status
        FROM claims
        WHERE {where_sql}
        ORDER BY claim_id ASC
    """

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return rows if rows is not None else []


def _validate_depth(depth: int) -> list[str]:
    """Validate supported graph traversal depths."""
    if depth not in {1, 2}:
        return ["depth must be 1 or 2."]
    return []


def _connected_entity_ids_from_claims(
    claim_rows: list[dict[str, Any]],
    *,
    seed_entity_id: str,
) -> set[str]:
    """Return one-hop entity ids connected to the seed by the given claims."""
    connected_entity_ids: set[str] = set()
    for row in claim_rows:
        subject_id = row["subject_entity_id"]
        object_id = row["object_entity_id"]
        if subject_id != seed_entity_id:
            connected_entity_ids.add(subject_id)
        if object_id != seed_entity_id:
            connected_entity_ids.add(object_id)
    return connected_entity_ids


def _dedupe_and_limit_claim_rows(
    claim_rows: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Dedupe claim rows by claim_id, sort deterministically, then apply limit."""
    deduped_by_claim_id: dict[str, dict[str, Any]] = {}
    for row in claim_rows:
        deduped_by_claim_id[row["claim_id"]] = row

    sorted_rows = sorted(deduped_by_claim_id.values(), key=lambda row: row["claim_id"])
    return sorted_rows[:limit]


def _collect_graph_claim_rows(
    conn: Connection[Any],
    *,
    seed_entity_id: str,
    depth: int,
    predicate: str | None,
    confidence_min: float | None,
    evidence_status: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Collect filtered graph claim rows for one- or two-hop expansion."""
    depth_1_rows = _fetch_claim_edges(
        conn,
        touching_entity_ids={seed_entity_id},
        predicate=predicate,
        confidence_min=confidence_min,
        evidence_status=evidence_status,
    )

    if depth == 1:
        return _dedupe_and_limit_claim_rows(depth_1_rows, limit=limit)

    one_hop_entity_ids = _connected_entity_ids_from_claims(
        depth_1_rows,
        seed_entity_id=seed_entity_id,
    )
    depth_2_rows = _fetch_claim_edges(
        conn,
        touching_entity_ids=one_hop_entity_ids,
        predicate=predicate,
        confidence_min=confidence_min,
        evidence_status=evidence_status,
    )

    return _dedupe_and_limit_claim_rows(depth_1_rows + depth_2_rows, limit=limit)


def _build_graph_response(
    conn: Connection[Any],
    *,
    seed_entity_id: str,
    depth: int,
    predicate: str | None,
    confidence_min: float | None,
    evidence_status: str | None,
    limit: int,
) -> GraphResponse:
    """Build a seed-centered graph response with deterministic traversal."""
    seed_row = _fetch_entity_by_id(conn, seed_entity_id)
    if seed_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seed entity not found for id '{seed_entity_id}'.",
        )

    edge_rows = _collect_graph_claim_rows(
        conn,
        seed_entity_id=seed_entity_id,
        depth=depth,
        predicate=predicate,
        confidence_min=confidence_min,
        evidence_status=evidence_status,
        limit=limit,
    )

    all_entity_ids: set[str] = {seed_entity_id}
    for row in edge_rows:
        all_entity_ids.add(row["subject_entity_id"])
        all_entity_ids.add(row["object_entity_id"])

    node_rows = _fetch_entities_by_ids(conn, all_entity_ids)
    if seed_entity_id not in {row["entity_id"] for row in node_rows}:
        node_rows = [seed_row, *node_rows]

    return GraphResponse(
        seed_entity_id=seed_entity_id,
        depth=depth,
        nodes=transform_entity_rows_to_nodes(node_rows),
        edges=transform_claim_rows_to_edges(edge_rows),
    )


@router.get("/graph", response_model=GraphResponse)
def get_graph(
    seed_entity_id: str = Query(..., pattern=r"^ENT-\d{4}$"),
    depth: int = Query(default=1),
    predicate: str | None = Query(default=None),
    confidence_min: float | None = Query(default=None, ge=0.0, le=1.0),
    evidence_status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    conn: Connection[Any] = Depends(get_db_connection),
) -> GraphResponse:
    """Return a seed-centered graph neighborhood for one entity."""
    normalized_seed_entity_id = _trim_or_none(seed_entity_id)
    normalized_predicate = _trim_or_none(predicate)
    normalized_evidence_status = _trim_or_none(evidence_status)

    if normalized_seed_entity_id is None or not ENT_ID_PATTERN.match(normalized_seed_entity_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=["seed_entity_id must match ENT-####."],
        )

    depth_errors = _validate_depth(depth)
    if depth_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=depth_errors,
        )

    if predicate is not None and normalized_predicate is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=["predicate cannot be blank when provided."],
        )
    if evidence_status is not None and normalized_evidence_status is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=["evidence_status cannot be blank when provided."],
        )

    try:
        if normalized_predicate is not None:
            predicate_errors = validate_predicate_usage(normalized_predicate)
            if predicate_errors:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=predicate_errors,
                )

        return _build_graph_response(
            conn,
            seed_entity_id=normalized_seed_entity_id,
            depth=depth,
            predicate=normalized_predicate,
            confidence_min=confidence_min,
            evidence_status=normalized_evidence_status,
            limit=limit,
        )
    except PredicateCatalogUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Predicate validation rules are unavailable. Ensure ontology "
                "relationship_types can be loaded."
            ),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc
