"""Claim endpoints.

Current scope:
- Read a single claim by ``claim_id``.
- Create a new claim.
- Update an existing claim via PATCH.
- Delete a claim with self-reference safety checks.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path as ApiPath, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from psycopg import Connection, errors as pg_errors

from api.claim_reference_validation import (
    validate_source_asset_fields,
    validate_source_asset_id_shapes,
)
from api.claim_relationship_validation import (
    validate_claim_link_id_shapes,
    validate_claim_link_references,
)
from api.claim_validation import (
    PredicateCatalogUnavailableError,
    validate_predicate_usage,
)
from api.db import get_db_connection

router = APIRouter(prefix="/claims", tags=["claims"])

ENT_ID_PATTERN = re.compile(r"^ENT-\d{4}$")


class ClaimReadResponse(BaseModel):
    """Response model for claim reads."""

    claim_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    evidence_status: str | None = None
    confidence: float | None = None
    source_id: str | None = None
    asset_id: str | None = None
    locator: str | None = None
    note: str | None = None
    review_status: str | None = None
    claim_status: str | None = None
    supersedes_claim_id: str | None = None
    contradicts_claim_id: str | None = None
    subject_entity: dict[str, Any] | None = None
    object_entity: dict[str, Any] | None = None
    source: dict[str, Any] | None = None
    asset: dict[str, Any] | None = None


class ClaimCreateRequest(BaseModel):
    """Request payload for claim creation."""

    subject_entity_id: str
    predicate: str
    object_entity_id: str
    source_id: str
    evidence_status: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    asset_id: str | None = None
    locator: str | None = None
    note: str | None = None
    review_status: str | None = None
    claim_status: str | None = None
    supersedes_claim_id: str | None = None
    contradicts_claim_id: str | None = None


class ClaimUpdateRequest(BaseModel):
    """Request payload for partial claim updates."""

    subject_entity_id: str | None = None
    predicate: str | None = None
    object_entity_id: str | None = None
    source_id: str | None = None
    evidence_status: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    asset_id: str | None = None
    locator: str | None = None
    note: str | None = None
    review_status: str | None = None
    claim_status: str | None = None
    supersedes_claim_id: str | None = None
    contradicts_claim_id: str | None = None


class ClaimDeleteSuccessResponse(BaseModel):
    """Response payload for successful claim deletion."""

    deleted: bool
    claim_id: str


class ClaimDeleteConflictResponse(BaseModel):
    """Response payload when deletion is blocked by claim references."""

    deleted: bool
    claim_id: str
    reason: str
    supersedes_references: int
    contradicts_references: int
    total_references: int


def _trim_or_none(value: str | None) -> str | None:
    """Trim whitespace and convert empty strings to None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _fetch_by_claim_id(conn: Connection[Any], claim_id: str) -> dict[str, Any] | None:
    """Fetch one claim by primary key."""
    sql = """
        SELECT
            claim_id,
            subject_entity_id,
            predicate,
            object_entity_id,
            evidence_status,
            confidence,
            source_id,
            asset_id,
            locator,
            note,
            review_status,
            claim_status,
            supersedes_claim_id,
            contradicts_claim_id
        FROM claims
        WHERE claim_id = %(claim_id)s
        LIMIT 1;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"claim_id": claim_id})
        return cur.fetchone()


def _list_claims(
    conn: Connection[Any],
    *,
    predicate: str | None,
    confidence_min: float | None,
    confidence_max: float | None,
    evidence_status: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """List claims with optional filters and stable ordering."""
    where_clauses: list[str] = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if predicate is not None:
        where_clauses.append("predicate = %(predicate)s")
        params["predicate"] = predicate

    if confidence_min is not None:
        where_clauses.append("confidence >= %(confidence_min)s")
        params["confidence_min"] = confidence_min

    if confidence_max is not None:
        where_clauses.append("confidence <= %(confidence_max)s")
        params["confidence_max"] = confidence_max

    if evidence_status is not None:
        where_clauses.append("evidence_status = %(evidence_status)s")
        params["evidence_status"] = evidence_status

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

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
            locator,
            note,
            review_status,
            claim_status,
            supersedes_claim_id,
            contradicts_claim_id
        FROM claims
        {where_sql}
        ORDER BY claim_id ASC
        LIMIT %(limit)s
        OFFSET %(offset)s;
    """

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return rows if rows is not None else []


def _validate_confidence_bounds(
    confidence_min: float | None,
    confidence_max: float | None,
) -> list[str]:
    """Validate confidence range bounds for list filtering."""
    if (
        confidence_min is not None
        and confidence_max is not None
        and confidence_min > confidence_max
    ):
        return ["confidence_min cannot be greater than confidence_max."]
    return []


def _id_exists(conn: Connection[Any], *, table: str, column: str, value: str) -> bool:
    """Check whether a referenced ID exists."""
    allowed_pairs = {
        ("entities", "entity_id"),
        ("sources", "source_id"),
        ("source_assets", "asset_id"),
        ("claims", "claim_id"),
    }
    if (table, column) not in allowed_pairs:
        raise ValueError(f"Unsupported lookup table/column: {table}.{column}")

    sql = f"SELECT 1 FROM {table} WHERE {column} = %(value)s LIMIT 1;"
    with conn.cursor() as cur:
        cur.execute(sql, {"value": value})
        return cur.fetchone() is not None


def _normalize_claim_create_input(payload: ClaimCreateRequest) -> tuple[dict[str, Any], list[str]]:
    """Normalize and validate claim create payload."""
    errors: list[str] = []

    normalized = {
        "subject_entity_id": _trim_or_none(payload.subject_entity_id),
        "predicate": _trim_or_none(payload.predicate),
        "object_entity_id": _trim_or_none(payload.object_entity_id),
        "evidence_status": _trim_or_none(payload.evidence_status),
        "confidence": payload.confidence,
        "source_id": _trim_or_none(payload.source_id),
        "asset_id": _trim_or_none(payload.asset_id),
        "locator": _trim_or_none(payload.locator),
        "note": _trim_or_none(payload.note),
        "review_status": _trim_or_none(payload.review_status),
        "claim_status": _trim_or_none(payload.claim_status),
        "supersedes_claim_id": _trim_or_none(payload.supersedes_claim_id),
        "contradicts_claim_id": _trim_or_none(payload.contradicts_claim_id),
    }

    subject_id = normalized["subject_entity_id"]
    predicate = normalized["predicate"]
    object_id = normalized["object_entity_id"]
    source_id = normalized["source_id"]
    asset_id = normalized["asset_id"]

    if subject_id is None or not ENT_ID_PATTERN.match(subject_id):
        errors.append("subject_entity_id must match ENT-####.")

    if object_id is None or not ENT_ID_PATTERN.match(object_id):
        errors.append("object_entity_id must match ENT-####.")

    errors.extend(
        validate_source_asset_id_shapes(
            source_id=source_id,
            asset_id=asset_id,
            source_required=True,
        )
    )

    errors.extend(validate_predicate_usage(predicate))

    errors.extend(
        validate_claim_link_id_shapes(
            normalized["supersedes_claim_id"],
            normalized["contradicts_claim_id"],
        )
    )

    return normalized, errors


def _normalize_claim_patch_input(payload: ClaimUpdateRequest) -> tuple[dict[str, Any], list[str]]:
    """Normalize and validate partial claim update payload."""
    errors: list[str] = []
    patch_payload = payload.model_dump(exclude_unset=True)
    normalized_patch: dict[str, Any] = {}

    string_fields = (
        "subject_entity_id",
        "predicate",
        "object_entity_id",
        "source_id",
        "evidence_status",
        "asset_id",
        "locator",
        "note",
        "review_status",
        "claim_status",
        "supersedes_claim_id",
        "contradicts_claim_id",
    )
    for field in string_fields:
        if field in patch_payload:
            normalized_patch[field] = _trim_or_none(patch_payload[field])

    if "confidence" in patch_payload:
        normalized_patch["confidence"] = patch_payload["confidence"]

    if "subject_entity_id" in normalized_patch:
        subject_id = normalized_patch["subject_entity_id"]
        if subject_id is None:
            errors.append("subject_entity_id cannot be blank.")
        elif not ENT_ID_PATTERN.match(subject_id):
            errors.append("subject_entity_id must match ENT-####.")

    if "object_entity_id" in normalized_patch:
        object_id = normalized_patch["object_entity_id"]
        if object_id is None:
            errors.append("object_entity_id cannot be blank.")
        elif not ENT_ID_PATTERN.match(object_id):
            errors.append("object_entity_id must match ENT-####.")

    if "source_id" in normalized_patch or "asset_id" in normalized_patch:
        source_for_shape = normalized_patch.get("source_id")
        asset_for_shape = normalized_patch.get("asset_id")
        if "source_id" not in normalized_patch:
            source_for_shape = None
        if "asset_id" not in normalized_patch:
            asset_for_shape = None
        errors.extend(
            validate_source_asset_id_shapes(
                source_id=source_for_shape,
                asset_id=asset_for_shape,
                source_required="source_id" in normalized_patch,
            )
        )

    if "predicate" in normalized_patch:
        predicate = normalized_patch["predicate"]
        if predicate is None:
            errors.append("predicate cannot be blank.")
        else:
            errors.extend(validate_predicate_usage(predicate))

    if "supersedes_claim_id" in normalized_patch or "contradicts_claim_id" in normalized_patch:
        errors.extend(
            validate_claim_link_id_shapes(
                normalized_patch.get("supersedes_claim_id"),
                normalized_patch.get("contradicts_claim_id"),
            )
        )

    return normalized_patch, errors


def _merge_claim_patch(current_row: dict[str, Any], patch_values: dict[str, Any]) -> dict[str, Any]:
    """Merge current claim row with normalized patch fields."""
    merged = {
        "subject_entity_id": current_row.get("subject_entity_id"),
        "predicate": current_row.get("predicate"),
        "object_entity_id": current_row.get("object_entity_id"),
        "evidence_status": current_row.get("evidence_status"),
        "confidence": current_row.get("confidence"),
        "source_id": current_row.get("source_id"),
        "asset_id": current_row.get("asset_id"),
        "locator": current_row.get("locator"),
        "note": current_row.get("note"),
        "review_status": current_row.get("review_status"),
        "claim_status": current_row.get("claim_status"),
        "supersedes_claim_id": current_row.get("supersedes_claim_id"),
        "contradicts_claim_id": current_row.get("contradicts_claim_id"),
    }
    merged.update(patch_values)
    return merged


def _validate_claim_merged_values(
    values: dict[str, Any],
    *,
    claim_id: str,
) -> list[str]:
    """Validate merged claim values before persistence."""
    errors: list[str] = []

    subject_id = values.get("subject_entity_id")
    object_id = values.get("object_entity_id")
    source_id = values.get("source_id")
    predicate = values.get("predicate")
    asset_id = values.get("asset_id")
    supersedes_id = values.get("supersedes_claim_id")
    contradicts_id = values.get("contradicts_claim_id")

    if not isinstance(subject_id, str) or not ENT_ID_PATTERN.match(subject_id):
        errors.append("subject_entity_id must match ENT-####.")
    if not isinstance(object_id, str) or not ENT_ID_PATTERN.match(object_id):
        errors.append("object_entity_id must match ENT-####.")
    if not isinstance(source_id, str):
        errors.append("source_id is required.")
    else:
        errors.extend(
            validate_source_asset_id_shapes(
                source_id=source_id,
                asset_id=asset_id if isinstance(asset_id, str) else None,
                source_required=True,
            )
        )
    if not isinstance(predicate, str) or predicate.strip() == "":
        errors.append("predicate is required.")
    else:
        errors.extend(validate_predicate_usage(predicate))

    if asset_id is not None and not isinstance(asset_id, str):
        errors.append("asset_id must be a string when provided.")

    if supersedes_id is not None and not isinstance(supersedes_id, str):
        errors.append("supersedes_claim_id must be a string when provided.")
    if contradicts_id is not None and not isinstance(contradicts_id, str):
        errors.append("contradicts_claim_id must be a string when provided.")
    if isinstance(supersedes_id, str) or isinstance(contradicts_id, str):
        errors.extend(
            validate_claim_link_id_shapes(
                supersedes_id if isinstance(supersedes_id, str) else None,
                contradicts_id if isinstance(contradicts_id, str) else None,
                current_claim_id=claim_id,
            )
        )

    return errors


def _validate_reference_ids(conn: Connection[Any], values: dict[str, Any]) -> list[str]:
    """Validate foreign-key-like references for clearer API errors."""
    errors: list[str] = []

    subject_id = values.get("subject_entity_id")
    object_id = values.get("object_entity_id")
    supersedes_id = values.get("supersedes_claim_id")
    contradicts_id = values.get("contradicts_claim_id")

    if isinstance(subject_id, str) and not _id_exists(
        conn, table="entities", column="entity_id", value=subject_id
    ):
        errors.append(f"subject_entity_id '{subject_id}' does not exist.")

    if isinstance(object_id, str) and not _id_exists(
        conn, table="entities", column="entity_id", value=object_id
    ):
        errors.append(f"object_entity_id '{object_id}' does not exist.")

    errors.extend(validate_source_asset_fields(conn, values, source_required=True))

    errors.extend(
        validate_claim_link_references(
            conn,
            supersedes_id if isinstance(supersedes_id, str) else None,
            contradicts_id if isinstance(contradicts_id, str) else None,
        )
    )

    return errors


def generate_claim_id(conn: Connection[Any]) -> str:
    """Generate next CLM-#### ID from current max claim ID.

    Note:
        This ``max + 1`` strategy is acceptable now but not concurrency-safe at
        high write volume. Future improvement: DB sequence or UUID-based IDs.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(MAX(CAST(SUBSTRING(claim_id FROM 5) AS INT)), 0)
            FROM claims
            WHERE claim_id ~ '^CLM-[0-9]{4}$';
            """
        )
        max_num_row = cur.fetchone()
        next_num = int(max_num_row[0]) + 1 if max_num_row else 1

        while True:
            candidate = f"CLM-{next_num:04d}"
            cur.execute(
                "SELECT 1 FROM claims WHERE claim_id = %(claim_id)s LIMIT 1;",
                {"claim_id": candidate},
            )
            if cur.fetchone() is None:
                return candidate
            next_num += 1


def _insert_claim(
    conn: Connection[Any],
    *,
    claim_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Insert claim row and return created record."""
    sql = """
        INSERT INTO claims (
            claim_id,
            subject_entity_id,
            predicate,
            object_entity_id,
            evidence_status,
            confidence,
            source_id,
            asset_id,
            locator,
            note,
            review_status,
            claim_status,
            supersedes_claim_id,
            contradicts_claim_id
        )
        VALUES (
            %(claim_id)s,
            %(subject_entity_id)s,
            %(predicate)s,
            %(object_entity_id)s,
            %(evidence_status)s,
            %(confidence)s,
            %(source_id)s,
            %(asset_id)s,
            %(locator)s,
            %(note)s,
            %(review_status)s,
            %(claim_status)s,
            %(supersedes_claim_id)s,
            %(contradicts_claim_id)s
        )
        RETURNING
            claim_id,
            subject_entity_id,
            predicate,
            object_entity_id,
            evidence_status,
            confidence,
            source_id,
            asset_id,
            locator,
            note,
            review_status,
            claim_status,
            supersedes_claim_id,
            contradicts_claim_id;
    """
    params = dict(values)
    params["claim_id"] = claim_id
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("Insert succeeded but no claim row was returned.")
    return row


def _update_claim(
    conn: Connection[Any],
    *,
    claim_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Update claim row and return updated record."""
    sql = """
        UPDATE claims
        SET
            subject_entity_id = %(subject_entity_id)s,
            predicate = %(predicate)s,
            object_entity_id = %(object_entity_id)s,
            evidence_status = %(evidence_status)s,
            confidence = %(confidence)s,
            source_id = %(source_id)s,
            asset_id = %(asset_id)s,
            locator = %(locator)s,
            note = %(note)s,
            review_status = %(review_status)s,
            claim_status = %(claim_status)s,
            supersedes_claim_id = %(supersedes_claim_id)s,
            contradicts_claim_id = %(contradicts_claim_id)s
        WHERE claim_id = %(claim_id)s
        RETURNING
            claim_id,
            subject_entity_id,
            predicate,
            object_entity_id,
            evidence_status,
            confidence,
            source_id,
            asset_id,
            locator,
            note,
            review_status,
            claim_status,
            supersedes_claim_id,
            contradicts_claim_id;
    """
    params = dict(values)
    params["claim_id"] = claim_id
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("Update succeeded but no claim row was returned.")
    return row


def _claim_exists(conn: Connection[Any], claim_id: str) -> bool:
    """Return True when the claim exists."""
    return _fetch_by_claim_id(conn, claim_id) is not None


def _count_claim_references(conn: Connection[Any], claim_id: str) -> tuple[int, int, int]:
    """Count references where other claims point to this claim."""
    sql = """
        SELECT
            COUNT(*) FILTER (
                WHERE supersedes_claim_id = %(claim_id)s
            ) AS supersedes_references,
            COUNT(*) FILTER (
                WHERE contradicts_claim_id = %(claim_id)s
            ) AS contradicts_references
        FROM claims
        WHERE supersedes_claim_id = %(claim_id)s OR contradicts_claim_id = %(claim_id)s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"claim_id": claim_id})
        row = cur.fetchone()

    if row is None:
        return 0, 0, 0

    supersedes_refs = int(row["supersedes_references"] or 0)
    contradicts_refs = int(row["contradicts_references"] or 0)
    total_refs = supersedes_refs + contradicts_refs
    return supersedes_refs, contradicts_refs, total_refs


def _delete_claim(conn: Connection[Any], claim_id: str) -> bool:
    """Delete a claim by ID and return whether a row was deleted."""
    sql = "DELETE FROM claims WHERE claim_id = %(claim_id)s;"
    with conn.cursor() as cur:
        cur.execute(sql, {"claim_id": claim_id})
        return cur.rowcount > 0


@router.get("/{claim_id}", response_model=ClaimReadResponse)
def get_claim(
    claim_id: str = ApiPath(
        ...,
        pattern=r"^CLM-\d{4}$",
        description="Claim ID in CLM-#### format.",
    ),
    conn: Connection[Any] = Depends(get_db_connection),
) -> ClaimReadResponse:
    """Get a claim by exact claim_id."""
    try:
        row = _fetch_by_claim_id(conn, claim_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim not found for id '{claim_id}'.",
        )

    return ClaimReadResponse(**row)


@router.get("", response_model=list[ClaimReadResponse])
def list_claims(
    predicate: str | None = Query(default=None),
    confidence_min: float | None = Query(default=None, ge=0.0, le=1.0),
    confidence_max: float | None = Query(default=None, ge=0.0, le=1.0),
    evidence_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    conn: Connection[Any] = Depends(get_db_connection),
) -> list[ClaimReadResponse]:
    """List claims with optional predicate/confidence/evidence_status filters."""
    normalized_predicate = _trim_or_none(predicate)
    normalized_evidence_status = _trim_or_none(evidence_status)

    try:
        confidence_errors = _validate_confidence_bounds(confidence_min, confidence_max)
        if confidence_errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=confidence_errors,
            )

        if normalized_predicate is not None:
            predicate_errors = validate_predicate_usage(normalized_predicate)
            if predicate_errors:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=predicate_errors,
                )

        rows = _list_claims(
            conn,
            predicate=normalized_predicate,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            evidence_status=normalized_evidence_status,
            limit=limit,
            offset=offset,
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

    return [ClaimReadResponse(**row) for row in rows]


@router.post("", response_model=ClaimReadResponse, status_code=status.HTTP_201_CREATED)
def create_claim(
    payload: ClaimCreateRequest,
    conn: Connection[Any] = Depends(get_db_connection),
) -> ClaimReadResponse:
    """Create a new claim and return created record."""
    try:
        normalized, errors = _normalize_claim_create_input(payload)
    except PredicateCatalogUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Predicate validation rules are unavailable. Ensure ontology "
                "relationship_types can be loaded."
            ),
        ) from exc

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors,
        )

    try:
        with conn.transaction():
            claim_id = generate_claim_id(conn)

            claim_link_errors = validate_claim_link_id_shapes(
                normalized.get("supersedes_claim_id"),
                normalized.get("contradicts_claim_id"),
                current_claim_id=claim_id,
            )
            if claim_link_errors:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=claim_link_errors,
                )

            reference_errors = _validate_reference_ids(conn, normalized)
            if reference_errors:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=reference_errors,
                )

            row = _insert_claim(conn, claim_id=claim_id, values=normalized)

    except pg_errors.UniqueViolation as exc:
        constraint_name = getattr(exc.diag, "constraint_name", None)
        if constraint_name == "uq_claims_spo_source":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Claim with the same (subject_entity_id, predicate, "
                    "object_entity_id, source_id) already exists."
                ),
            ) from exc
        if constraint_name == "claims_pkey":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Generated claim_id collided with existing row. Please retry.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claim create failed due to a uniqueness conflict.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc

    return ClaimReadResponse(**row)


@router.patch("/{claim_id}", response_model=ClaimReadResponse)
def update_claim(
    payload: ClaimUpdateRequest,
    claim_id: str = ApiPath(
        ...,
        pattern=r"^CLM-\d{4}$",
        description="Claim ID in CLM-#### format.",
    ),
    conn: Connection[Any] = Depends(get_db_connection),
) -> ClaimReadResponse:
    """Partially update a claim by claim_id."""
    current_row = _fetch_by_claim_id(conn, claim_id)
    if current_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim not found for id '{claim_id}'.",
        )

    try:
        patch_values, patch_errors = _normalize_claim_patch_input(payload)
    except PredicateCatalogUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Predicate validation rules are unavailable. Ensure ontology "
                "relationship_types can be loaded."
            ),
        ) from exc

    if patch_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=patch_errors,
        )

    merged_values = _merge_claim_patch(current_row, patch_values)
    try:
        validation_errors = _validate_claim_merged_values(merged_values, claim_id=claim_id)
    except PredicateCatalogUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Predicate validation rules are unavailable. Ensure ontology "
                "relationship_types can be loaded."
            ),
        ) from exc
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=validation_errors,
        )

    try:
        reference_errors = _validate_reference_ids(conn, merged_values)
        if reference_errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=reference_errors,
            )

        with conn.transaction():
            updated_row = _update_claim(conn, claim_id=claim_id, values=merged_values)

    except pg_errors.UniqueViolation as exc:
        constraint_name = getattr(exc.diag, "constraint_name", None)
        if constraint_name == "uq_claims_spo_source":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Update would create duplicate "
                    "(subject_entity_id, predicate, object_entity_id, source_id)."
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claim update failed due to a uniqueness conflict.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc

    return ClaimReadResponse(**updated_row)


@router.delete(
    "/{claim_id}",
    response_model=ClaimDeleteSuccessResponse,
    responses={409: {"model": ClaimDeleteConflictResponse}},
)
def delete_claim(
    claim_id: str = ApiPath(
        ...,
        pattern=r"^CLM-\d{4}$",
        description="Claim ID in CLM-#### format.",
    ),
    conn: Connection[Any] = Depends(get_db_connection),
) -> ClaimDeleteSuccessResponse | JSONResponse:
    """Delete a claim if it is not referenced by other claims."""
    try:
        if not _claim_exists(conn, claim_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim not found for id '{claim_id}'.",
            )

        supersedes_refs, contradicts_refs, total_refs = _count_claim_references(conn, claim_id)
        if total_refs > 0:
            conflict_payload = ClaimDeleteConflictResponse(
                deleted=False,
                claim_id=claim_id,
                reason="Claim is still referenced by other claims.",
                supersedes_references=supersedes_refs,
                contradicts_references=contradicts_refs,
                total_references=total_refs,
            )
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=conflict_payload.model_dump(),
            )

        with conn.transaction():
            deleted = _delete_claim(conn, claim_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim not found for id '{claim_id}'.",
            )

        return ClaimDeleteSuccessResponse(deleted=True, claim_id=claim_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc
