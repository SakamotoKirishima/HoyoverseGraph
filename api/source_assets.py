"""Source asset CRUD endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path as ApiPath, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from psycopg import Connection, errors as pg_errors

from api.db import get_db_connection
from api.source_asset_validation import (
    ASSET_ID_PATTERN,
    SOURCE_ID_PATTERN,
    derive_asset_domain_from_source_id,
    merge_asset_patch,
    normalize_asset_create_payload,
    normalize_asset_patch_payload,
    validate_source_asset_linkage,
    validate_asset_values,
)

router = APIRouter(prefix="/source-assets", tags=["source-assets"])


class SourceSummary(BaseModel):
    """Lightweight source summary nested under source-asset responses."""

    source_id: str
    title: str
    source_type: str
    source_format: str
    game: str | None = None
    scope: str | None = None
    reliability_tier: str | None = None


class SourceAssetResponse(BaseModel):
    """Source-asset-centered response shape."""

    asset_id: str
    source_id: str
    asset_type: str
    file_path_or_url: str | None = None
    locator: str | None = None
    description: str | None = None
    is_primary_evidence: bool | None = None
    notes: str | None = None
    source: SourceSummary | None = None


class SourceAssetProvenanceClaimSummary(BaseModel):
    """Compact claim summary for asset provenance traversal."""

    claim_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    source_id: str | None = None
    locator: str | None = None
    evidence_status: str | None = None
    confidence: float | None = None
    claim_status: str | None = None


class SourceAssetProvenanceResponse(BaseModel):
    """Source-asset provenance response with lightweight source and citing claims."""

    asset_id: str
    source_id: str
    asset_type: str
    file_path_or_url: str | None = None
    locator: str | None = None
    description: str | None = None
    is_primary_evidence: bool | None = None
    notes: str | None = None
    source: SourceSummary | None = None
    claims: list[SourceAssetProvenanceClaimSummary]


class SourceAssetCreateRequest(BaseModel):
    """Request payload for source-asset creation."""

    source_id: str
    asset_type: str
    file_path_or_url: str | None = None
    locator: str | None = None
    description: str | None = None
    is_primary_evidence: bool | None = None
    notes: str | None = None


class SourceAssetUpdateRequest(BaseModel):
    """Request payload for source-asset partial updates."""

    source_id: str | None = None
    asset_type: str | None = None
    file_path_or_url: str | None = None
    locator: str | None = None
    description: str | None = None
    is_primary_evidence: bool | None = None
    notes: str | None = None


class SourceAssetDeleteSuccessResponse(BaseModel):
    """Delete success payload."""

    deleted: bool
    asset_id: str


class SourceAssetDeleteConflictResponse(BaseModel):
    """Delete blocked payload when claims reference an asset."""

    deleted: bool
    asset_id: str
    reason: str
    claim_references: int


def _fetch_asset_by_id(conn: Connection[Any], asset_id: str) -> dict[str, Any] | None:
    """Fetch one asset row by primary key."""
    sql = """
        SELECT
            asset_id,
            source_id,
            asset_type,
            file_path_or_url,
            locator,
            description,
            is_primary_evidence,
            notes
        FROM source_assets
        WHERE asset_id = %(asset_id)s
        LIMIT 1;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"asset_id": asset_id})
        return cur.fetchone()


def _fetch_source_summary(conn: Connection[Any], source_id: str) -> dict[str, Any] | None:
    """Fetch lightweight source summary used by source-asset responses."""
    sql = """
        SELECT
            source_id,
            title,
            source_type,
            source_format,
            game,
            scope,
            reliability_tier
        FROM sources
        WHERE source_id = %(source_id)s
        LIMIT 1;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"source_id": source_id})
        return cur.fetchone()


def _source_exists(conn: Connection[Any], source_id: str) -> bool:
    """Return True when a source exists."""
    return _fetch_source_summary(conn, source_id) is not None


def _insert_asset(
    conn: Connection[Any],
    *,
    asset_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Insert one source asset and return inserted row."""
    sql = """
        INSERT INTO source_assets (
            asset_id,
            source_id,
            asset_type,
            file_path_or_url,
            locator,
            description,
            is_primary_evidence,
            notes
        )
        VALUES (
            %(asset_id)s,
            %(source_id)s,
            %(asset_type)s,
            %(file_path_or_url)s,
            %(locator)s,
            %(description)s,
            %(is_primary_evidence)s,
            %(notes)s
        )
        RETURNING
            asset_id,
            source_id,
            asset_type,
            file_path_or_url,
            locator,
            description,
            is_primary_evidence,
            notes;
    """
    params = dict(values)
    params["asset_id"] = asset_id
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("Asset insert succeeded but no row was returned.")
    return row


def _update_asset(
    conn: Connection[Any],
    *,
    asset_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Update one source asset and return updated row."""
    sql = """
        UPDATE source_assets
        SET
            source_id = %(source_id)s,
            asset_type = %(asset_type)s,
            file_path_or_url = %(file_path_or_url)s,
            locator = %(locator)s,
            description = %(description)s,
            is_primary_evidence = %(is_primary_evidence)s,
            notes = %(notes)s
        WHERE asset_id = %(asset_id)s
        RETURNING
            asset_id,
            source_id,
            asset_type,
            file_path_or_url,
            locator,
            description,
            is_primary_evidence,
            notes;
    """
    params = dict(values)
    params["asset_id"] = asset_id
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("Asset update succeeded but no row was returned.")
    return row


def _count_claim_asset_references(conn: Connection[Any], asset_id: str) -> int:
    """Count inbound claim references to an asset."""
    sql = "SELECT COUNT(*) AS ref_count FROM claims WHERE asset_id = %(asset_id)s;"
    with conn.cursor() as cur:
        cur.execute(sql, {"asset_id": asset_id})
        row = cur.fetchone()
    return int(row["ref_count"] or 0) if row else 0


def _fetch_provenance_claims_by_asset_id(
    conn: Connection[Any], asset_id: str
) -> list[dict[str, Any]]:
    """Fetch compact provenance claim summaries for one source asset."""
    sql = """
        SELECT
            claim_id,
            subject_entity_id,
            predicate,
            object_entity_id,
            source_id,
            locator,
            evidence_status,
            confidence,
            claim_status
        FROM claims
        WHERE asset_id = %(asset_id)s
        ORDER BY claim_id ASC;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"asset_id": asset_id})
        rows = cur.fetchall()
    return rows if rows is not None else []


def _delete_asset(conn: Connection[Any], asset_id: str) -> bool:
    """Delete one asset row and return whether deletion occurred."""
    sql = "DELETE FROM source_assets WHERE asset_id = %(asset_id)s;"
    with conn.cursor() as cur:
        cur.execute(sql, {"asset_id": asset_id})
        return cur.rowcount > 0


def generate_asset_id(conn: Connection[Any], *, domain: str) -> str:
    """Generate next AST-{DOMAIN}-#### value.

    Note:
        This max+1 strategy is acceptable for now but is not concurrency-safe
        under heavy concurrent writes. A sequence-based allocator is preferred
        long-term.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(MAX(CAST(split_part(asset_id, '-', 3) AS INT)), 0) AS max_num
            FROM source_assets
            WHERE asset_id ~ %(pattern)s;
            """,
            {"pattern": rf"^AST-{domain}-[0-9]{{4}}$"},
        )
        row = cur.fetchone()
        next_num = int(row["max_num"]) + 1 if row else 1

        while True:
            candidate = f"AST-{domain}-{next_num:04d}"
            cur.execute(
                "SELECT 1 FROM source_assets WHERE asset_id = %(asset_id)s LIMIT 1;",
                {"asset_id": candidate},
            )
            if cur.fetchone() is None:
                return candidate
            next_num += 1


def _to_response(
    asset_row: dict[str, Any],
    source_row: dict[str, Any] | None,
) -> SourceAssetResponse:
    """Map DB rows to API response model."""
    source_summary = SourceSummary(**source_row) if source_row is not None else None
    return SourceAssetResponse(**asset_row, source=source_summary)


@router.get("/{asset_id}", response_model=SourceAssetResponse)
def get_source_asset(
    asset_id: str = ApiPath(
        ...,
        pattern=ASSET_ID_PATTERN.pattern,
        description="Asset ID in AST-{DOMAIN}-#### format.",
    ),
    conn: Connection[Any] = Depends(get_db_connection),
) -> SourceAssetResponse:
    """Read one source asset by asset_id."""
    try:
        asset_row = _fetch_asset_by_id(conn, asset_id)
        if asset_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source asset not found for id '{asset_id}'.",
            )
        source_row = _fetch_source_summary(conn, asset_row["source_id"])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc

    return _to_response(asset_row, source_row)


@router.get("/{asset_id}/provenance", response_model=SourceAssetProvenanceResponse)
def get_source_asset_provenance(
    asset_id: str = ApiPath(
        ...,
        pattern=ASSET_ID_PATTERN.pattern,
        description="Asset ID in AST-{DOMAIN}-#### format.",
    ),
    conn: Connection[Any] = Depends(get_db_connection),
) -> SourceAssetProvenanceResponse:
    """Read source-asset provenance with compact claim citations."""
    try:
        asset_row = _fetch_asset_by_id(conn, asset_id)
        if asset_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source asset not found for id '{asset_id}'.",
            )

        source_row = _fetch_source_summary(conn, asset_row["source_id"])
        claim_rows = _fetch_provenance_claims_by_asset_id(conn, asset_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc

    source_summary = SourceSummary(**source_row) if source_row is not None else None
    return SourceAssetProvenanceResponse(
        **asset_row,
        source=source_summary,
        claims=[SourceAssetProvenanceClaimSummary(**row) for row in claim_rows],
    )


@router.post("", response_model=SourceAssetResponse, status_code=status.HTTP_201_CREATED)
def create_source_asset(
    payload: SourceAssetCreateRequest,
    conn: Connection[Any] = Depends(get_db_connection),
) -> SourceAssetResponse:
    """Create a source asset row."""
    normalized = normalize_asset_create_payload(payload.model_dump())
    errors = validate_asset_values(normalized)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)

    source_id = normalized["source_id"]
    if not isinstance(source_id, str):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=["source_id must match SRC-{DOMAIN}-####."],
        )

    source_row = _fetch_source_summary(conn, source_id)
    if source_row is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[f"source_id '{source_id}' does not exist."],
        )

    linkage_errors = validate_source_asset_linkage(source_row, normalized)
    if linkage_errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=linkage_errors)

    domain = derive_asset_domain_from_source_id(source_id)
    if domain is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=["source_id must match SRC-{DOMAIN}-####."],
        )

    try:
        with conn.transaction():
            asset_id = generate_asset_id(conn, domain=domain)
            inserted_row = _insert_asset(conn, asset_id=asset_id, values=normalized)
    except pg_errors.UniqueViolation as exc:
        constraint_name = getattr(exc.diag, "constraint_name", None)
        if constraint_name == "uq_source_assets_dedupe_fingerprint":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Source asset already exists with the same "
                    "(source_id, asset_type, file_path_or_url, locator)."
                ),
            ) from exc
        if constraint_name == "source_assets_pkey":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Generated asset_id collided with existing row. Please retry.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source asset create failed due to a uniqueness conflict.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc

    return _to_response(inserted_row, source_row)


@router.patch("/{asset_id}", response_model=SourceAssetResponse)
def update_source_asset(
    payload: SourceAssetUpdateRequest,
    asset_id: str = ApiPath(
        ...,
        pattern=ASSET_ID_PATTERN.pattern,
        description="Asset ID in AST-{DOMAIN}-#### format.",
    ),
    conn: Connection[Any] = Depends(get_db_connection),
) -> SourceAssetResponse:
    """Partially update a source asset."""
    current_row = _fetch_asset_by_id(conn, asset_id)
    if current_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source asset not found for id '{asset_id}'.",
        )

    patch_values = normalize_asset_patch_payload(payload.model_dump(exclude_unset=True))
    merged_values = merge_asset_patch(current_row, patch_values)
    errors = validate_asset_values(merged_values)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)

    merged_source_id = merged_values.get("source_id")
    if not isinstance(merged_source_id, str) or not SOURCE_ID_PATTERN.match(merged_source_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=["source_id must match SRC-{DOMAIN}-####."],
        )

    source_row = _fetch_source_summary(conn, merged_source_id)
    if source_row is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[f"source_id '{merged_source_id}' does not exist."],
        )

    linkage_errors = validate_source_asset_linkage(source_row, merged_values)
    if linkage_errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=linkage_errors)

    try:
        with conn.transaction():
            updated_row = _update_asset(conn, asset_id=asset_id, values=merged_values)
    except pg_errors.UniqueViolation as exc:
        constraint_name = getattr(exc.diag, "constraint_name", None)
        if constraint_name == "uq_source_assets_dedupe_fingerprint":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Update would create duplicate source asset fingerprint for "
                    "(source_id, asset_type, file_path_or_url, locator)."
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source asset update failed due to a uniqueness conflict.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc

    return _to_response(updated_row, source_row)


@router.delete(
    "/{asset_id}",
    response_model=SourceAssetDeleteSuccessResponse,
    responses={409: {"model": SourceAssetDeleteConflictResponse}},
)
def delete_source_asset(
    asset_id: str = ApiPath(
        ...,
        pattern=ASSET_ID_PATTERN.pattern,
        description="Asset ID in AST-{DOMAIN}-#### format.",
    ),
    conn: Connection[Any] = Depends(get_db_connection),
) -> SourceAssetDeleteSuccessResponse | JSONResponse:
    """Delete one source asset only if no claims reference it."""
    try:
        if _fetch_asset_by_id(conn, asset_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source asset not found for id '{asset_id}'.",
            )

        claim_refs = _count_claim_asset_references(conn, asset_id)
        if claim_refs > 0:
            payload = SourceAssetDeleteConflictResponse(
                deleted=False,
                asset_id=asset_id,
                reason="Source asset is still referenced by claims.",
                claim_references=claim_refs,
            )
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=payload.model_dump(),
            )

        with conn.transaction():
            deleted = _delete_asset(conn, asset_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source asset not found for id '{asset_id}'.",
            )

        return SourceAssetDeleteSuccessResponse(deleted=True, asset_id=asset_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc
