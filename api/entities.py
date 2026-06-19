"""Entity endpoints.

Current scope:
- Read a single entity by ``entity_id`` or by slug.
- Create a new entity.
- Update an existing entity via PATCH.
- Delete an entity with claim-reference safety checks.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from psycopg import Connection, errors as pg_errors

from api.db import get_db_connection
from api.entity_validation import (
    PRIMARY_SCOPE_ALLOWED,
    deserialize_aliases,
    get_allowed_entity_types,
    merge_entity_patch,
    normalize_primary_scope_game,
    validate_entity_patch_payload,
    validate_entity_payload_for_create,
    validate_merged_entity_values,
)

router = APIRouter(prefix="/entities", tags=["entities"])

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_EDGE_HYPHEN_RE = re.compile(r"(^-+|-+$)")


class EntityReadResponse(BaseModel):
    """Response model for entity reads."""

    entity_id: str
    canonical_name: str
    entity_type: str
    primary_scope_game: str | None = None
    display_label: str | None = None
    aliases_pipe_delimited: str | None = None
    short_description: str | None = None
    starter_status: str | None = None
    notes: str | None = None
    slug: str


class EntityCreateRequest(BaseModel):
    """Request payload for creating an entity."""

    canonical_name: str = Field(..., description="Canonical entity name.")
    entity_type: str = Field(..., description="Ontology entity type code.")
    primary_scope_game: str | None = None
    display_label: str | None = None
    aliases: list[str] | None = None
    short_description: str | None = None
    starter_status: str | None = None
    notes: str | None = None


class EntityUpdateRequest(BaseModel):
    """Request payload for partial entity updates.

    All fields are optional. Route logic uses ``model_dump(exclude_unset=True)``
    to preserve PATCH semantics (omitted vs explicit null).
    """

    canonical_name: str | None = None
    entity_type: str | None = None
    primary_scope_game: str | None = None
    display_label: str | None = None
    aliases: list[str] | None = None
    short_description: str | None = None
    starter_status: str | None = None
    notes: str | None = None


class EntityCreateResponse(BaseModel):
    """Response payload for created/updated entity."""

    entity_id: str
    canonical_name: str
    entity_type: str
    primary_scope_game: str | None = None
    display_label: str | None = None
    aliases: list[str] = Field(default_factory=list)
    short_description: str | None = None
    starter_status: str | None = None
    notes: str | None = None


class EntityDeleteSuccessResponse(BaseModel):
    """Response payload for successful entity deletion."""

    deleted: bool
    entity_id: str


class EntityDeleteConflictResponse(BaseModel):
    """Response payload when entity deletion is blocked by claim references."""

    deleted: bool
    entity_id: str
    reason: str
    subject_references: int
    object_references: int
    total_references: int


def _slugify(value: str) -> str:
    """Create a URL-safe slug from a string."""
    lowered = value.strip().lower()
    collapsed = _NON_ALNUM_RE.sub("-", lowered)
    return _EDGE_HYPHEN_RE.sub("", collapsed)


def _choose_slug_source(row: dict[str, Any]) -> str:
    """Pick the best name source for deterministic entity slugs."""
    display_label = row.get("display_label")
    canonical_name = row.get("canonical_name")
    if isinstance(display_label, str) and display_label.strip():
        return display_label
    if isinstance(canonical_name, str) and canonical_name.strip():
        return canonical_name
    return str(row.get("entity_id", ""))


def _row_to_response(row: dict[str, Any]) -> EntityReadResponse:
    """Map a DB row to API response payload."""
    return EntityReadResponse(
        entity_id=row["entity_id"],
        canonical_name=row["canonical_name"],
        entity_type=row["entity_type"],
        primary_scope_game=row.get("primary_scope_game"),
        display_label=row.get("display_label"),
        aliases_pipe_delimited=row.get("aliases_pipe_delimited"),
        short_description=row.get("short_description"),
        starter_status=row.get("starter_status"),
        notes=row.get("notes"),
        slug=_slugify(_choose_slug_source(row)),
    )


def _fetch_by_entity_id(conn: Connection[Any], entity_id: str) -> dict[str, Any] | None:
    """Fetch one entity by primary key."""
    sql = """
        SELECT
            entity_id,
            canonical_name,
            entity_type,
            primary_scope_game,
            display_label,
            aliases_pipe_delimited,
            short_description,
            starter_status,
            notes
        FROM entities
        WHERE entity_id = %(entity_id)s
        LIMIT 1;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"entity_id": entity_id})
        return cur.fetchone()


def _entity_exists(conn: Connection[Any], entity_id: str) -> bool:
    """Return True when the entity exists."""
    return _fetch_by_entity_id(conn, entity_id) is not None


def _fetch_by_slug(conn: Connection[Any], slug: str) -> list[dict[str, Any]]:
    """Fetch entities whose canonical/display slug matches provided slug."""
    sql = """
        SELECT
            entity_id,
            canonical_name,
            entity_type,
            primary_scope_game,
            display_label,
            aliases_pipe_delimited,
            short_description,
            starter_status,
            notes
        FROM entities
        WHERE
            regexp_replace(
                regexp_replace(lower(coalesce(canonical_name, '')), '[^a-z0-9]+', '-', 'g'),
                '(^-+|-+$)',
                '',
                'g'
            ) = %(slug)s
            OR regexp_replace(
                regexp_replace(lower(coalesce(display_label, '')), '[^a-z0-9]+', '-', 'g'),
                '(^-+|-+$)',
                '',
                'g'
            ) = %(slug)s
        ORDER BY entity_id
        LIMIT 2;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"slug": slug})
        rows = cur.fetchall()
    return rows if rows is not None else []


def _fetch_by_canonical_or_display(
    conn: Connection[Any],
    lookup_value: str,
) -> list[dict[str, Any]]:
    """Fetch entities by exact canonical_name/display_label (case-insensitive)."""
    sql = """
        SELECT
            entity_id,
            canonical_name,
            entity_type,
            primary_scope_game,
            display_label,
            aliases_pipe_delimited,
            short_description,
            starter_status,
            notes
        FROM entities
        WHERE
            lower(canonical_name) = lower(%(lookup_value)s)
            OR lower(coalesce(display_label, '')) = lower(%(lookup_value)s)
        ORDER BY canonical_name ASC, entity_id ASC
        LIMIT 5;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"lookup_value": lookup_value})
        rows = cur.fetchall()
    return rows if rows is not None else []


def _minimal_match_payload(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Create a minimal ambiguity payload for conflict responses."""
    return [
        {
            "entity_id": str(row.get("entity_id", "")),
            "canonical_name": str(row.get("canonical_name", "")),
        }
        for row in rows
    ]


def _resolve_entity_by_lookup_value(
    conn: Connection[Any],
    lookup_value: str,
) -> dict[str, Any]:
    """Resolve entity by canonical/display first, then slug fallback."""
    normalized_lookup = lookup_value.strip()
    if not normalized_lookup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found for lookup '{lookup_value}'.",
        )

    exact_matches = _fetch_by_canonical_or_display(conn, normalized_lookup)
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Lookup value resolved to multiple entities via canonical/display match.",
                "matches": _minimal_match_payload(exact_matches),
            },
        )

    normalized_slug = _slugify(normalized_lookup)
    if not normalized_slug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found for lookup '{lookup_value}'.",
        )

    slug_matches = _fetch_by_slug(conn, normalized_slug)
    if len(slug_matches) == 1:
        return slug_matches[0]
    if len(slug_matches) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Lookup value resolved to multiple entities via slug match.",
                "matches": _minimal_match_payload(slug_matches),
            },
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Entity not found for lookup '{lookup_value}'.",
    )


def _list_entities(
    conn: Connection[Any],
    *,
    entity_type: str | None,
    primary_scope_game: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """List entities with optional filters and stable ordering."""
    where_clauses: list[str] = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if entity_type is not None:
        where_clauses.append("entity_type = %(entity_type)s")
        params["entity_type"] = entity_type

    if primary_scope_game is not None:
        where_clauses.append("primary_scope_game = %(primary_scope_game)s")
        params["primary_scope_game"] = primary_scope_game

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    sql = f"""
        SELECT
            entity_id,
            canonical_name,
            entity_type,
            primary_scope_game,
            display_label,
            aliases_pipe_delimited,
            short_description,
            starter_status,
            notes
        FROM entities
        {where_sql}
        ORDER BY canonical_name ASC, entity_id ASC
        LIMIT %(limit)s
        OFFSET %(offset)s;
    """

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return rows if rows is not None else []


def generate_entity_id(conn: Connection[Any]) -> str:
    """Generate the next ENT-#### ID from the current max value.

    Note:
        This ``max + 1`` strategy is acceptable for now but is not safe under
        high concurrency. Future improvement: use a DB sequence or UUID-based IDs.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(MAX(CAST(SUBSTRING(entity_id FROM 5) AS INT)), 0)
            FROM entities
            WHERE entity_id ~ '^ENT-[0-9]{4}$';
            """
        )
        max_id_num_row = cur.fetchone()
        next_num = int(max_id_num_row[0]) + 1 if max_id_num_row else 1

        while True:
            candidate = f"ENT-{next_num:04d}"
            cur.execute(
                "SELECT 1 FROM entities WHERE entity_id = %(entity_id)s LIMIT 1;",
                {"entity_id": candidate},
            )
            if cur.fetchone() is None:
                return candidate
            next_num += 1


def _insert_entity(
    conn: Connection[Any],
    *,
    entity_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Insert entity row and return created record."""
    sql = """
        INSERT INTO entities (
            entity_id,
            canonical_name,
            entity_type,
            primary_scope_game,
            display_label,
            aliases_pipe_delimited,
            short_description,
            starter_status,
            notes
        )
        VALUES (
            %(entity_id)s,
            %(canonical_name)s,
            %(entity_type)s,
            %(primary_scope_game)s,
            %(display_label)s,
            %(aliases_pipe_delimited)s,
            %(short_description)s,
            %(starter_status)s,
            %(notes)s
        )
        RETURNING
            entity_id,
            canonical_name,
            entity_type,
            primary_scope_game,
            display_label,
            aliases_pipe_delimited,
            short_description,
            starter_status,
            notes;
    """
    params = dict(values)
    params["entity_id"] = entity_id
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("Insert succeeded but no row was returned.")
    return row


def _update_entity(
    conn: Connection[Any],
    *,
    entity_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Update entity row and return updated record."""
    sql = """
        UPDATE entities
        SET
            canonical_name = %(canonical_name)s,
            entity_type = %(entity_type)s,
            primary_scope_game = %(primary_scope_game)s,
            display_label = %(display_label)s,
            aliases_pipe_delimited = %(aliases_pipe_delimited)s,
            short_description = %(short_description)s,
            starter_status = %(starter_status)s,
            notes = %(notes)s
        WHERE entity_id = %(entity_id)s
        RETURNING
            entity_id,
            canonical_name,
            entity_type,
            primary_scope_game,
            display_label,
            aliases_pipe_delimited,
            short_description,
            starter_status,
            notes;
    """
    params = dict(values)
    params["entity_id"] = entity_id
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("Update completed but no row was returned.")
    return row


def _count_claim_references(conn: Connection[Any], entity_id: str) -> tuple[int, int, int]:
    """Count claim references where entity_id appears as subject/object."""
    sql = """
        SELECT
            COUNT(*) FILTER (WHERE subject_entity_id = %(entity_id)s) AS subject_references,
            COUNT(*) FILTER (WHERE object_entity_id = %(entity_id)s) AS object_references
        FROM claims
        WHERE subject_entity_id = %(entity_id)s OR object_entity_id = %(entity_id)s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"entity_id": entity_id})
        row = cur.fetchone()

    if row is None:
        return 0, 0, 0

    subject_refs = int(row["subject_references"] or 0)
    object_refs = int(row["object_references"] or 0)
    total_refs = subject_refs + object_refs
    return subject_refs, object_refs, total_refs


def _delete_entity(conn: Connection[Any], entity_id: str) -> bool:
    """Delete an entity by ID and return whether a row was deleted."""
    sql = "DELETE FROM entities WHERE entity_id = %(entity_id)s;"
    with conn.cursor() as cur:
        cur.execute(sql, {"entity_id": entity_id})
        return cur.rowcount > 0


def _row_to_create_response(row: dict[str, Any]) -> EntityCreateResponse:
    """Map DB row to create/update response model."""
    return EntityCreateResponse(
        entity_id=row["entity_id"],
        canonical_name=row["canonical_name"],
        entity_type=row["entity_type"],
        primary_scope_game=row.get("primary_scope_game"),
        display_label=row.get("display_label"),
        aliases=deserialize_aliases(row.get("aliases_pipe_delimited")),
        short_description=row.get("short_description"),
        starter_status=row.get("starter_status"),
        notes=row.get("notes"),
    )


@router.get("", response_model=list[EntityCreateResponse])
def list_entities(
    entity_type: str | None = Query(default=None),
    primary_scope_game: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    conn: Connection[Any] = Depends(get_db_connection),
) -> list[EntityCreateResponse]:
    """List entities with optional entity_type and primary_scope_game filters."""
    normalized_entity_type = entity_type.strip() if isinstance(entity_type, str) else None
    if normalized_entity_type == "":
        normalized_entity_type = None

    allowed_entity_types = get_allowed_entity_types()
    if (
        normalized_entity_type is not None
        and allowed_entity_types
        and normalized_entity_type not in allowed_entity_types
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"entity_type '{normalized_entity_type}' is not defined in ontology entity_types.",
        )

    normalized_scope = normalize_primary_scope_game(primary_scope_game)
    if normalized_scope is not None and normalized_scope not in PRIMARY_SCOPE_ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "primary_scope_game must be one of: "
                "Honkai Impact 3, Honkai: Star Rail, Genshin Impact, Gun Girls Z, Multi."
            ),
        )

    try:
        rows = _list_entities(
            conn,
            entity_type=normalized_entity_type,
            primary_scope_game=normalized_scope,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc

    return [_row_to_create_response(row) for row in rows]


@router.get("/lookup/{value}", response_model=EntityCreateResponse)
def lookup_entity(
    value: str,
    conn: Connection[Any] = Depends(get_db_connection),
) -> EntityCreateResponse:
    """Resolve an entity by canonical/display lookup with slug fallback."""
    try:
        row = _resolve_entity_by_lookup_value(conn, value)
        return _row_to_create_response(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc


@router.get("/{entity_id}", response_model=EntityReadResponse)
def get_entity(
    entity_id: str = Path(
        ...,
        pattern=r"^ENT-\d{4}$",
        description="Entity ID in ENT-#### format.",
    ),
    conn: Connection[Any] = Depends(get_db_connection),
) -> EntityReadResponse:
    """Get an entity by exact entity_id."""
    row = _fetch_by_entity_id(conn, entity_id)
    if row is not None:
        return _row_to_response(row)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Entity not found for id '{entity_id}'.",
    )


@router.get("/slug/{slug}", response_model=EntityReadResponse)
def get_entity_by_slug(
    slug: str,
    conn: Connection[Any] = Depends(get_db_connection),
) -> EntityReadResponse:
    """Get an entity explicitly by slug.

    This endpoint avoids ID-first behavior and only resolves slug matches.
    """
    normalized_slug = _slugify(slug)
    if not normalized_slug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found for slug '{slug}'.",
        )

    slug_matches = _fetch_by_slug(conn, normalized_slug)
    if not slug_matches:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found for slug '{slug}'.",
        )
    if len(slug_matches) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Ambiguous slug '{normalized_slug}'. Multiple entities matched; "
                "use entity_id for deterministic lookup."
            ),
        )

    return _row_to_response(slug_matches[0])


@router.post(
    "",
    response_model=EntityCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_entity(
    payload: EntityCreateRequest,
    conn: Connection[Any] = Depends(get_db_connection),
) -> EntityCreateResponse:
    """Create a new entity and return created record."""
    normalized, validation_errors = validate_entity_payload_for_create(payload.model_dump())
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=validation_errors,
        )

    try:
        with conn.transaction():
            entity_id = generate_entity_id(conn)
            row = _insert_entity(conn, entity_id=entity_id, values=normalized)
    except pg_errors.UniqueViolation as exc:
        constraint_name = getattr(exc.diag, "constraint_name", None)
        if constraint_name == "uq_entities_canonical_name_entity_type":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("Entity with the same (canonical_name, entity_type) already exists."),
            ) from exc
        if constraint_name == "entities_pkey":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Generated entity_id collided with existing row. Please retry.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Entity create failed due to a uniqueness conflict.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc

    return _row_to_create_response(row)


@router.patch(
    "/{entity_id}",
    response_model=EntityCreateResponse,
)
def update_entity(
    payload: EntityUpdateRequest,
    entity_id: str = Path(
        ...,
        pattern=r"^ENT-\d{4}$",
        description="Entity ID in ENT-#### format.",
    ),
    conn: Connection[Any] = Depends(get_db_connection),
) -> EntityCreateResponse:
    """Partially update an entity by entity_id."""
    current_row = _fetch_by_entity_id(conn, entity_id)
    if current_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found for id '{entity_id}'.",
        )

    patch_values, patch_errors = validate_entity_patch_payload(
        payload.model_dump(exclude_unset=True)
    )
    if patch_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=patch_errors,
        )

    merged_values = merge_entity_patch(current_row, patch_values)
    validation_errors = validate_merged_entity_values(merged_values)
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=validation_errors,
        )

    try:
        with conn.transaction():
            updated_row = _update_entity(conn, entity_id=entity_id, values=merged_values)
    except pg_errors.UniqueViolation as exc:
        constraint_name = getattr(exc.diag, "constraint_name", None)
        if constraint_name == "uq_entities_canonical_name_entity_type":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("Update would create duplicate (canonical_name, entity_type)."),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Entity update failed due to a uniqueness conflict.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc

    return _row_to_create_response(updated_row)


@router.delete(
    "/{entity_id}",
    response_model=EntityDeleteSuccessResponse,
    responses={409: {"model": EntityDeleteConflictResponse}},
)
def delete_entity(
    entity_id: str = Path(
        ...,
        pattern=r"^ENT-\d{4}$",
        description="Entity ID in ENT-#### format.",
    ),
    conn: Connection[Any] = Depends(get_db_connection),
) -> EntityDeleteSuccessResponse | JSONResponse:
    """Delete an entity if it is not referenced by claims.

    Future place for force-delete/archive behavior can be added here.
    """
    try:
        if not _entity_exists(conn, entity_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity not found for id '{entity_id}'.",
            )

        subject_refs, object_refs, total_refs = _count_claim_references(conn, entity_id)
        if total_refs > 0:
            conflict_payload = EntityDeleteConflictResponse(
                deleted=False,
                entity_id=entity_id,
                reason="Entity is still referenced by claims.",
                subject_references=subject_refs,
                object_references=object_refs,
                total_references=total_refs,
            )
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=conflict_payload.model_dump(),
            )

        with conn.transaction():
            deleted = _delete_entity(conn, entity_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity not found for id '{entity_id}'.",
            )

        return EntityDeleteSuccessResponse(deleted=True, entity_id=entity_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected database error: {exc}",
        ) from exc
