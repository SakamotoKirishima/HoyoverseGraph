"""Source endpoints.

Current scope:
- Read a single source by ``source_id``.
- Create a source record.
- Include linked assets and lightweight claim provenance summaries.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Path as ApiPath, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from psycopg import Connection, errors as pg_errors

from api.db import get_db_connection
from api.entity_validation import PRIMARY_SCOPE_ALLOWED, normalize_primary_scope_game
from api.source_validation import (
    is_web_like_source_format,
    normalize_source_format,
    normalize_source_type,
    validate_source_format,
    validate_source_type,
)

router = APIRouter(prefix="/sources", tags=["sources"])

SOURCE_ID_PATTERN = r"^SRC-(?:HI3|HSR|GI|GGZ|WIKI|HL|INT|GEN)-\d{4}$"
RELIABILITY_TIER_ALLOWED: set[str] = {"tier_1", "tier_2", "tier_3", "tier_4"}
ALLOWED_RELIABILITY_BY_SOURCE_TYPE: dict[str, set[str]] = {
    "official_story": {"tier_1", "tier_2"},
    "official_databank": {"tier_1", "tier_2"},
    "official_profile": {"tier_1", "tier_2"},
    "official_companion": {"tier_1", "tier_2"},
    "community_wiki": {"tier_2", "tier_3", "tier_4"},
    "community_reference": {"tier_3"},
    "datamine": {"tier_3"},
    "internal_editorial": {"tier_4"},
    "other": {"tier_3", "tier_4"},
}
GAME_TO_DOMAIN: dict[str, str] = {
    "Honkai Impact 3": "HI3",
    "Honkai: Star Rail": "HSR",
    "Genshin Impact": "GI",
    "Gun Girls Z": "GGZ",
}


class SourceAssetSummary(BaseModel):
    """Asset summary for source provenance responses."""

    asset_id: str
    asset_type: str
    file_path_or_url: str | None = None
    locator: str | None = None
    description: str | None = None
    is_primary_evidence: bool | None = None
    notes: str | None = None


class SourceProvenanceClaimSummary(BaseModel):
    """Compact claim summary for provenance lookups."""

    claim_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    asset_id: str | None = None
    locator: str | None = None
    claim_status: str | None = None


class SourceProvenanceAssetSummary(BaseModel):
    """Lightweight source-asset summary used in source provenance responses."""

    asset_id: str
    asset_type: str
    locator: str | None = None
    description: str | None = None
    is_primary_evidence: bool | None = None


class SourceProvenanceClaimDetail(BaseModel):
    """Compact provenance claim details for source-centric evidence navigation."""

    claim_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    asset_id: str | None = None
    locator: str | None = None
    evidence_status: str | None = None
    confidence: float | None = None
    claim_status: str | None = None


class SourceProvenanceResponse(BaseModel):
    """Source provenance response with linked assets and compact citing claims."""

    source_id: str
    title: str
    source_type: str
    source_format: str
    game: str | None = None
    scope: str | None = None
    reliability_tier: str | None = None
    assets: list[SourceProvenanceAssetSummary] = Field(default_factory=list)
    claims: list[SourceProvenanceClaimDetail] = Field(default_factory=list)


class SourceReadResponse(BaseModel):
    """Source read response with linked assets and claim provenance summaries."""

    source_id: str
    title: str
    url: str | None = None
    source_type: str
    source_format: str
    game: str | None = None
    scope: str | None = None
    reliability_tier: str | None = None
    language: str | None = None
    publication_date: date | None = None
    notes: str | None = None
    assets: list[SourceAssetSummary] = Field(default_factory=list)
    claims: list[SourceProvenanceClaimSummary] = Field(default_factory=list)


class SourceCreateRequest(BaseModel):
    """Request payload for creating a source."""

    title: str
    url: str | None = None
    source_type: str
    source_format: str
    game: str | None = None
    scope: str | None = None
    reliability_tier: str | None = None
    language: str | None = None
    publication_date: date | None = None
    notes: str | None = None


class SourceUpdateRequest(BaseModel):
    """Request payload for partial source updates."""

    title: str | None = None
    url: str | None = None
    source_type: str | None = None
    source_format: str | None = None
    game: str | None = None
    scope: str | None = None
    reliability_tier: str | None = None
    language: str | None = None
    publication_date: date | None = None
    notes: str | None = None


class SourceDeleteSuccessResponse(BaseModel):
    """Response payload for successful source deletion."""

    deleted: bool
    source_id: str


class SourceDeleteConflictResponse(BaseModel):
    """Response payload when source deletion is blocked by references."""

    deleted: bool
    source_id: str
    reason: str
    asset_references: int
    claim_references: int
    total_references: int


def _trim_or_none(value: str | None) -> str | None:
    """Trim whitespace and convert empty strings to None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _is_plausible_url(value: str) -> bool:
    """Return True if URL appears to be an HTTP/HTTPS URL."""
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _derive_source_domain(values: dict[str, Any]) -> str:
    """Derive source ID domain from source context.

    Priority:
    1) explicit game mapping for major game families
    2) source_type/source_format fallbacks for wiki/companion/internal
    3) generic domain fallback
    """
    game = values.get("game")
    source_type = values.get("source_type")
    source_format = values.get("source_format")

    if isinstance(game, str) and game in GAME_TO_DOMAIN:
        return GAME_TO_DOMAIN[game]

    if source_type in {"community_wiki", "community_reference"} or source_format == "wiki":
        return "WIKI"

    if source_type == "official_companion" and is_web_like_source_format(source_format):
        return "HL"

    if source_type == "internal_editorial":
        return "INT"

    return "GEN"


def _normalize_source_create_payload(payload: SourceCreateRequest) -> tuple[dict[str, Any], list[str]]:
    """Normalize and validate source create payload."""
    errors: list[str] = []

    normalized = {
        "title": _trim_or_none(payload.title),
        "url": _trim_or_none(payload.url),
        "source_type": normalize_source_type(payload.source_type),
        "source_format": normalize_source_format(payload.source_format),
        "game": normalize_primary_scope_game(payload.game),
        "scope": _trim_or_none(payload.scope),
        "reliability_tier": _trim_or_none(payload.reliability_tier),
        "language": _trim_or_none(payload.language),
        "publication_date": payload.publication_date,
        "notes": _trim_or_none(payload.notes),
    }

    title = normalized["title"]
    source_type = normalized["source_type"]
    source_format = normalized["source_format"]
    reliability_tier = normalized["reliability_tier"]
    game = normalized["game"]
    url = normalized["url"]

    if title is None:
        errors.append("title is required and cannot be blank.")

    errors.extend(validate_source_type(source_type, required=True))
    errors.extend(validate_source_format(source_format, required=True))

    if reliability_tier is not None and reliability_tier not in RELIABILITY_TIER_ALLOWED:
        errors.append("reliability_tier must be one of: tier_1, tier_2, tier_3, tier_4.")

    if (
        source_type is not None
        and reliability_tier is not None
        and source_type in ALLOWED_RELIABILITY_BY_SOURCE_TYPE
        and reliability_tier not in ALLOWED_RELIABILITY_BY_SOURCE_TYPE[source_type]
    ):
        errors.append(
            f"reliability_tier '{reliability_tier}' is invalid for source_type '{source_type}'."
        )

    if isinstance(game, str) and game not in PRIMARY_SCOPE_ALLOWED:
        errors.append(
            "game must be one of: Honkai Impact 3, Honkai: Star Rail, "
            "Genshin Impact, Gun Girls Z, Multi."
        )

    if is_web_like_source_format(source_format) and url is None:
        errors.append(f"url is required when source_format is '{source_format}'.")

    if url is not None and not _is_plausible_url(url):
        errors.append("url must be a valid HTTP/HTTPS URL when provided.")

    return normalized, errors


def _normalize_source_patch_payload(payload: SourceUpdateRequest) -> dict[str, Any]:
    """Normalize only fields explicitly provided in PATCH payload."""
    patch_raw = payload.model_dump(exclude_unset=True)
    normalized_patch: dict[str, Any] = {}

    if "title" in patch_raw:
        normalized_patch["title"] = _trim_or_none(patch_raw["title"])
    if "url" in patch_raw:
        normalized_patch["url"] = _trim_or_none(patch_raw["url"])
    if "source_type" in patch_raw:
        normalized_patch["source_type"] = normalize_source_type(patch_raw["source_type"])
    if "source_format" in patch_raw:
        normalized_patch["source_format"] = normalize_source_format(patch_raw["source_format"])
    if "game" in patch_raw:
        normalized_patch["game"] = normalize_primary_scope_game(patch_raw["game"])
    if "scope" in patch_raw:
        normalized_patch["scope"] = _trim_or_none(patch_raw["scope"])
    if "reliability_tier" in patch_raw:
        normalized_patch["reliability_tier"] = _trim_or_none(patch_raw["reliability_tier"])
    if "language" in patch_raw:
        normalized_patch["language"] = _trim_or_none(patch_raw["language"])
    if "publication_date" in patch_raw:
        normalized_patch["publication_date"] = patch_raw["publication_date"]
    if "notes" in patch_raw:
        normalized_patch["notes"] = _trim_or_none(patch_raw["notes"])

    return normalized_patch


def _validate_source_values(values: dict[str, Any]) -> list[str]:
    """Validate normalized full source values."""
    errors: list[str] = []

    title = values.get("title")
    source_type = values.get("source_type")
    source_format = values.get("source_format")
    reliability_tier = values.get("reliability_tier")
    game = values.get("game")
    url = values.get("url")

    if not isinstance(title, str) or title.strip() == "":
        errors.append("title is required and cannot be blank.")

    errors.extend(validate_source_type(source_type, required=True))
    errors.extend(validate_source_format(source_format, required=True))

    if reliability_tier is not None and reliability_tier not in RELIABILITY_TIER_ALLOWED:
        errors.append("reliability_tier must be one of: tier_1, tier_2, tier_3, tier_4.")

    if (
        isinstance(source_type, str)
        and source_type in ALLOWED_RELIABILITY_BY_SOURCE_TYPE
        and reliability_tier is not None
        and reliability_tier not in ALLOWED_RELIABILITY_BY_SOURCE_TYPE[source_type]
    ):
        errors.append(
            f"reliability_tier '{reliability_tier}' is invalid for source_type '{source_type}'."
        )

    if isinstance(game, str) and game not in PRIMARY_SCOPE_ALLOWED:
        errors.append(
            "game must be one of: Honkai Impact 3, Honkai: Star Rail, "
            "Genshin Impact, Gun Girls Z, Multi."
        )

    if is_web_like_source_format(source_format) and url is None:
        errors.append(f"url is required when source_format is '{source_format}'.")

    if isinstance(url, str) and not _is_plausible_url(url):
        errors.append("url must be a valid HTTP/HTTPS URL when provided.")

    return errors


def _merge_source_patch(current_row: dict[str, Any], patch_values: dict[str, Any]) -> dict[str, Any]:
    """Merge current source row with normalized patch values."""
    merged = {
        "title": current_row.get("title"),
        "url": current_row.get("url"),
        "source_type": current_row.get("source_type"),
        "source_format": current_row.get("source_format"),
        "game": current_row.get("game"),
        "scope": current_row.get("scope"),
        "reliability_tier": current_row.get("reliability_tier"),
        "language": current_row.get("language"),
        "publication_date": current_row.get("publication_date"),
        "notes": current_row.get("notes"),
    }
    merged.update(patch_values)
    return merged


def _fetch_source_by_id(conn: Connection[Any], source_id: str) -> dict[str, Any] | None:
    """Fetch a single source row by source_id."""
    sql = """
        SELECT
            source_id,
            title,
            url,
            source_type,
            source_format,
            game,
            scope,
            reliability_tier,
            language,
            publication_date,
            notes
        FROM sources
        WHERE source_id = %(source_id)s
        LIMIT 1;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"source_id": source_id})
        return cur.fetchone()


def _source_exists(conn: Connection[Any], source_id: str) -> bool:
    """Return True when a source exists."""
    return _fetch_source_by_id(conn, source_id) is not None


def _fetch_assets_by_source_id(conn: Connection[Any], source_id: str) -> list[dict[str, Any]]:
    """Fetch all assets linked to a source."""
    sql = """
        SELECT
            asset_id,
            asset_type,
            file_path_or_url,
            locator,
            description,
            is_primary_evidence,
            notes
        FROM source_assets
        WHERE source_id = %(source_id)s
        ORDER BY is_primary_evidence DESC, asset_id ASC;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"source_id": source_id})
        rows = cur.fetchall()
    return rows if rows is not None else []


def _count_inbound_source_references(conn: Connection[Any], source_id: str) -> tuple[int, int, int]:
    """Count inbound source references from source_assets and claims."""
    sql = """
        SELECT
            (SELECT COUNT(*) FROM source_assets WHERE source_id = %(source_id)s) AS asset_references,
            (SELECT COUNT(*) FROM claims WHERE source_id = %(source_id)s) AS claim_references;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"source_id": source_id})
        row = cur.fetchone()

    if row is None:
        return 0, 0, 0

    asset_references = int(row["asset_references"] or 0)
    claim_references = int(row["claim_references"] or 0)
    total_references = asset_references + claim_references
    return asset_references, claim_references, total_references


def _fetch_claim_summaries_by_source_id(
    conn: Connection[Any], source_id: str
) -> list[dict[str, Any]]:
    """Fetch lightweight claim provenance rows for a source."""
    sql = """
        SELECT
            claim_id,
            subject_entity_id,
            predicate,
            object_entity_id,
            asset_id,
            locator,
            claim_status
        FROM claims
        WHERE source_id = %(source_id)s
        ORDER BY claim_id ASC;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"source_id": source_id})
        rows = cur.fetchall()
    return rows if rows is not None else []


def _fetch_provenance_assets_by_source_id(
    conn: Connection[Any], source_id: str
) -> list[dict[str, Any]]:
    """Fetch lightweight asset summaries for source provenance responses."""
    sql = """
        SELECT
            asset_id,
            asset_type,
            locator,
            description,
            is_primary_evidence
        FROM source_assets
        WHERE source_id = %(source_id)s
        ORDER BY is_primary_evidence DESC, asset_id ASC;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"source_id": source_id})
        rows = cur.fetchall()
    return rows if rows is not None else []


def _fetch_provenance_claims_by_source_id(
    conn: Connection[Any], source_id: str
) -> list[dict[str, Any]]:
    """Fetch compact provenance claim details for a source."""
    sql = """
        SELECT
            claim_id,
            subject_entity_id,
            predicate,
            object_entity_id,
            asset_id,
            locator,
            evidence_status,
            confidence,
            claim_status
        FROM claims
        WHERE source_id = %(source_id)s
        ORDER BY claim_id ASC;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"source_id": source_id})
        rows = cur.fetchall()
    return rows if rows is not None else []


def generate_source_id(conn: Connection[Any], *, domain: str) -> str:
    """Generate next source ID in one domain family.

    Note:
        This ``max + 1`` strategy is acceptable for now but is not safe under
        high concurrency. A sequence-based allocator should replace this later.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(MAX(CAST(split_part(source_id, '-', 3) AS INT)), 0) AS max_num
            FROM sources
            WHERE source_id ~ %(pattern)s;
            """,
            {"pattern": rf"^SRC-{domain}-[0-9]{{4}}$"},
        )
        row = cur.fetchone()
        next_num = int(row["max_num"]) + 1 if row else 1

        while True:
            candidate = f"SRC-{domain}-{next_num:04d}"
            cur.execute(
                "SELECT 1 FROM sources WHERE source_id = %(source_id)s LIMIT 1;",
                {"source_id": candidate},
            )
            if cur.fetchone() is None:
                return candidate
            next_num += 1


def _insert_source(
    conn: Connection[Any],
    *,
    source_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Insert a source row and return the inserted record."""
    sql = """
        INSERT INTO sources (
            source_id,
            title,
            url,
            source_type,
            source_format,
            game,
            scope,
            reliability_tier,
            language,
            publication_date,
            notes
        )
        VALUES (
            %(source_id)s,
            %(title)s,
            %(url)s,
            %(source_type)s,
            %(source_format)s,
            %(game)s,
            %(scope)s,
            %(reliability_tier)s,
            %(language)s,
            %(publication_date)s,
            %(notes)s
        )
        RETURNING
            source_id,
            title,
            url,
            source_type,
            source_format,
            game,
            scope,
            reliability_tier,
            language,
            publication_date,
            notes;
    """
    params = dict(values)
    params["source_id"] = source_id
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("Source insert succeeded but no row was returned.")
    return row


def _update_source(
    conn: Connection[Any],
    *,
    source_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Update source row and return updated record."""
    sql = """
        UPDATE sources
        SET
            title = %(title)s,
            url = %(url)s,
            source_type = %(source_type)s,
            source_format = %(source_format)s,
            game = %(game)s,
            scope = %(scope)s,
            reliability_tier = %(reliability_tier)s,
            language = %(language)s,
            publication_date = %(publication_date)s,
            notes = %(notes)s
        WHERE source_id = %(source_id)s
        RETURNING
            source_id,
            title,
            url,
            source_type,
            source_format,
            game,
            scope,
            reliability_tier,
            language,
            publication_date,
            notes;
    """
    params = dict(values)
    params["source_id"] = source_id
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("Source update succeeded but no row was returned.")
    return row


def _delete_source(conn: Connection[Any], source_id: str) -> bool:
    """Delete one source row and return whether deletion occurred."""
    sql = "DELETE FROM sources WHERE source_id = %(source_id)s;"
    with conn.cursor() as cur:
        cur.execute(sql, {"source_id": source_id})
        return cur.rowcount > 0


@router.get("/{source_id}", response_model=SourceReadResponse)
def get_source(
    source_id: str = ApiPath(
        ...,
        pattern=SOURCE_ID_PATTERN,
        description="Source ID in SRC-{DOMAIN}-#### format.",
    ),
    conn: Connection[Any] = Depends(get_db_connection),
) -> SourceReadResponse:
    """Get one source with linked assets and lightweight provenance claims."""
    try:
        source_row = _fetch_source_by_id(conn, source_id)
        if source_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source not found for id '{source_id}'.",
            )

        assets_rows = _fetch_assets_by_source_id(conn, source_id)
        claim_rows = _fetch_claim_summaries_by_source_id(conn, source_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc

    return SourceReadResponse(
        **source_row,
        assets=[SourceAssetSummary(**row) for row in assets_rows],
        claims=[SourceProvenanceClaimSummary(**row) for row in claim_rows],
    )


@router.get("/{source_id}/provenance", response_model=SourceProvenanceResponse)
def get_source_provenance(
    source_id: str = ApiPath(
        ...,
        pattern=SOURCE_ID_PATTERN,
        description="Source ID in SRC-{DOMAIN}-#### format.",
    ),
    conn: Connection[Any] = Depends(get_db_connection),
) -> SourceProvenanceResponse:
    """Get source provenance details: source, linked assets, and citing claims."""
    try:
        source_row = _fetch_source_by_id(conn, source_id)
        if source_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source not found for id '{source_id}'.",
            )

        asset_rows = _fetch_provenance_assets_by_source_id(conn, source_id)
        claim_rows = _fetch_provenance_claims_by_source_id(conn, source_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc

    return SourceProvenanceResponse(
        source_id=source_row["source_id"],
        title=source_row["title"],
        source_type=source_row["source_type"],
        source_format=source_row["source_format"],
        game=source_row.get("game"),
        scope=source_row.get("scope"),
        reliability_tier=source_row.get("reliability_tier"),
        assets=[SourceProvenanceAssetSummary(**row) for row in asset_rows],
        claims=[SourceProvenanceClaimDetail(**row) for row in claim_rows],
    )


@router.post("", response_model=SourceReadResponse, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: SourceCreateRequest,
    conn: Connection[Any] = Depends(get_db_connection),
) -> SourceReadResponse:
    """Create a source row and return source-centered response shape."""
    normalized, errors = _normalize_source_create_payload(payload)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors,
        )

    domain = _derive_source_domain(normalized)

    try:
        with conn.transaction():
            source_id = generate_source_id(conn, domain=domain)
            created_row = _insert_source(conn, source_id=source_id, values=normalized)
    except pg_errors.UniqueViolation as exc:
        constraint_name = getattr(exc.diag, "constraint_name", None)
        if constraint_name == "uq_sources_dedupe_fingerprint":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Source already exists with the same "
                    "(title, source_type, source_format, game, scope, language, publication_date)."
                ),
            ) from exc
        if constraint_name == "sources_pkey":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Generated source_id collided with existing row. Please retry.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source create failed due to a uniqueness conflict.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc

    return SourceReadResponse(
        **created_row,
        assets=[],
        claims=[],
    )


@router.patch("/{source_id}", response_model=SourceReadResponse)
def update_source(
    payload: SourceUpdateRequest,
    source_id: str = ApiPath(
        ...,
        pattern=SOURCE_ID_PATTERN,
        description="Source ID in SRC-{DOMAIN}-#### format.",
    ),
    conn: Connection[Any] = Depends(get_db_connection),
) -> SourceReadResponse:
    """Partially update a source and return source-centered response."""
    current_row = _fetch_source_by_id(conn, source_id)
    if current_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source not found for id '{source_id}'.",
        )

    patch_values = _normalize_source_patch_payload(payload)
    merged_values = _merge_source_patch(current_row, patch_values)
    validation_errors = _validate_source_values(merged_values)
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=validation_errors,
        )

    try:
        with conn.transaction():
            updated_row = _update_source(conn, source_id=source_id, values=merged_values)

        assets_rows = _fetch_assets_by_source_id(conn, source_id)
        claim_rows = _fetch_claim_summaries_by_source_id(conn, source_id)
    except pg_errors.UniqueViolation as exc:
        constraint_name = getattr(exc.diag, "constraint_name", None)
        if constraint_name == "uq_sources_dedupe_fingerprint":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Update would create duplicate source fingerprint for "
                    "(title, source_type, source_format, game, scope, language, publication_date)."
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source update failed due to a uniqueness conflict.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc

    return SourceReadResponse(
        **updated_row,
        assets=[SourceAssetSummary(**row) for row in assets_rows],
        claims=[SourceProvenanceClaimSummary(**row) for row in claim_rows],
    )


@router.delete(
    "/{source_id}",
    response_model=SourceDeleteSuccessResponse,
    responses={409: {"model": SourceDeleteConflictResponse}},
)
def delete_source(
    source_id: str = ApiPath(
        ...,
        pattern=SOURCE_ID_PATTERN,
        description="Source ID in SRC-{DOMAIN}-#### format.",
    ),
    conn: Connection[Any] = Depends(get_db_connection),
) -> SourceDeleteSuccessResponse | JSONResponse:
    """Delete a source only when there are no inbound asset/claim references."""
    try:
        if not _source_exists(conn, source_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source not found for id '{source_id}'.",
            )

        asset_refs, claim_refs, total_refs = _count_inbound_source_references(conn, source_id)
        if total_refs > 0:
            conflict_payload = SourceDeleteConflictResponse(
                deleted=False,
                source_id=source_id,
                reason="Source is still referenced by assets or claims.",
                asset_references=asset_refs,
                claim_references=claim_refs,
                total_references=total_refs,
            )
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=conflict_payload.model_dump(),
            )

        # Future place for force-delete or reassignment behavior if needed.
        with conn.transaction():
            deleted = _delete_source(conn, source_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source not found for id '{source_id}'.",
            )

        return SourceDeleteSuccessResponse(deleted=True, source_id=source_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc
