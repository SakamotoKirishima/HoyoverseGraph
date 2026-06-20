"""Entity search endpoint.

Current scope:
- Search entities by identity and descriptive text fields.
- Return lightweight, source-aware results using source_count.
- Support optional entity_type and primary_scope_game filters.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from psycopg import Connection

from api.db import get_db_connection
from api.entity_validation import (
    PRIMARY_SCOPE_ALLOWED,
    deserialize_aliases,
    get_allowed_entity_types,
    normalize_primary_scope_game,
)

router = APIRouter(tags=["search"])


class SearchResultResponse(BaseModel):
    """Entity search result response."""

    entity_id: str
    canonical_name: str
    display_label: str | None = None
    entity_type: str
    primary_scope_game: str | None = None
    aliases: list[str] = Field(default_factory=list)
    short_description: str | None = None
    source_count: int


def _normalized_text(value: str | None) -> str:
    """Normalize text for case-insensitive search comparisons."""
    if value is None:
        return ""
    return value.strip().casefold()


def _alias_values(row: dict[str, Any]) -> list[str]:
    """Deserialize aliases from a DB row for search matching."""
    return deserialize_aliases(row.get("aliases_pipe_delimited"))


def _matches_exact_alias(row: dict[str, Any], query: str) -> bool:
    """Return True when query matches an alias exactly, case-insensitively."""
    normalized_query = _normalized_text(query)
    return any(_normalized_text(alias) == normalized_query for alias in _alias_values(row))


def _matches_prefix_alias(row: dict[str, Any], query: str) -> bool:
    """Return True when query matches an alias prefix, case-insensitively."""
    normalized_query = _normalized_text(query)
    if not normalized_query:
        return False
    return any(_normalized_text(alias).startswith(normalized_query) for alias in _alias_values(row))


def _search_rank_bucket(row: dict[str, Any], query: str) -> int:
    """Return ranking bucket for one search row.

    Ranking order:
    1. exact canonical_name match
    2. exact display_label match
    3. exact alias match
    4. prefix canonical/display/alias match
    5. descriptive match in short_description or notes
    6. fallback for rows already selected by SQL but not matched by the
       simpler Python-side checks above
    """
    normalized_query = _normalized_text(query)
    canonical_name = _normalized_text(row.get("canonical_name"))
    display_label = _normalized_text(row.get("display_label"))
    short_description = _normalized_text(row.get("short_description"))
    notes = _normalized_text(row.get("notes"))

    if canonical_name == normalized_query:
        return 1
    if display_label == normalized_query:
        return 2
    if _matches_exact_alias(row, normalized_query):
        return 3
    if (
        canonical_name.startswith(normalized_query)
        or display_label.startswith(normalized_query)
        or _matches_prefix_alias(row, normalized_query)
    ):
        return 4
    if normalized_query and (normalized_query in short_description or normalized_query in notes):
        return 5
    return 6


def _sort_search_rows(rows: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Apply deterministic identity-first ranking to candidate search rows."""
    return sorted(
        rows,
        key=lambda row: (_search_rank_bucket(row, query), str(row.get("entity_id", ""))),
    )


def _row_to_search_result(row: dict[str, Any]) -> SearchResultResponse:
    """Map a DB row to the public search response shape."""
    return SearchResultResponse(
        entity_id=row["entity_id"],
        canonical_name=row["canonical_name"],
        display_label=row.get("display_label"),
        entity_type=row["entity_type"],
        primary_scope_game=row.get("primary_scope_game"),
        aliases=deserialize_aliases(row.get("aliases_pipe_delimited")),
        short_description=row.get("short_description"),
        source_count=int(row.get("source_count") or 0),
    )


def _validate_search_filters(
    *,
    entity_type: str | None,
    primary_scope_game: str | None,
) -> tuple[str | None, str | None]:
    """Validate and normalize optional search filters."""
    errors: list[str] = []

    normalized_entity_type: str | None = None
    if entity_type is not None:
        normalized_entity_type = entity_type.strip()
        if not normalized_entity_type:
            errors.append("entity_type cannot be blank when provided.")
        else:
            allowed_entity_types = get_allowed_entity_types()
            if allowed_entity_types and normalized_entity_type not in allowed_entity_types:
                errors.append(
                    f"entity_type '{normalized_entity_type}' is not defined in ontology entity_types."
                )

    normalized_primary_scope_game: str | None = None
    if primary_scope_game is not None:
        normalized_primary_scope_game = normalize_primary_scope_game(primary_scope_game)
        if normalized_primary_scope_game is None:
            errors.append("primary_scope_game cannot be blank when provided.")
        elif normalized_primary_scope_game not in PRIMARY_SCOPE_ALLOWED:
            errors.append(
                "primary_scope_game must be one of: "
                "Honkai Impact 3, Honkai: Star Rail, Genshin Impact, Gun Girls Z, Multi."
            )

    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)

    return normalized_entity_type, normalized_primary_scope_game


def _search_entities(
    conn: Connection[Any],
    *,
    q: str,
    entity_type: str | None,
    primary_scope_game: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """Search entities using identity-first ranking plus full-text fallback."""
    where_clauses: list[str] = []
    params: dict[str, Any] = {
        "q": q,
        "q_lower": q.casefold(),
        "prefix": f"{q.casefold()}%",
        "limit": limit,
        "offset": offset,
    }

    if entity_type is not None:
        where_clauses.append("sr.entity_type = %(entity_type)s")
        params["entity_type"] = entity_type

    if primary_scope_game is not None:
        where_clauses.append("sr.primary_scope_game = %(primary_scope_game)s")
        params["primary_scope_game"] = primary_scope_game

    where_sql = ""
    if where_clauses:
        where_sql = "AND " + " AND ".join(where_clauses)

    sql = f"""
        WITH source_counts AS (
            SELECT linked.entity_id, COUNT(DISTINCT linked.source_id)::INT AS source_count
            FROM (
                SELECT subject_entity_id AS entity_id, source_id
                FROM claims
                WHERE source_id IS NOT NULL
                UNION ALL
                SELECT object_entity_id AS entity_id, source_id
                FROM claims
                WHERE source_id IS NOT NULL
            ) AS linked
            GROUP BY linked.entity_id
        ),
        search_rows AS (
            SELECT
                e.entity_id,
                e.canonical_name,
                e.entity_type,
                e.primary_scope_game,
                e.display_label,
                e.aliases_pipe_delimited,
                e.short_description,
                e.notes,
                COALESCE(sc.source_count, 0) AS source_count,
                to_tsvector(
                    'simple',
                    COALESCE(e.canonical_name, '') || ' ' ||
                    COALESCE(e.display_label, '') || ' ' ||
                    COALESCE(e.aliases_pipe_delimited, '') || ' ' ||
                    COALESCE(e.short_description, '') || ' ' ||
                    COALESCE(e.notes, '')
                ) AS document
            FROM entities AS e
            LEFT JOIN source_counts AS sc
                ON sc.entity_id = e.entity_id
        )
        SELECT
            sr.entity_id,
            sr.canonical_name,
            sr.entity_type,
            sr.primary_scope_game,
            sr.display_label,
            sr.aliases_pipe_delimited,
            sr.short_description,
            sr.source_count
        FROM search_rows AS sr
        WHERE
            (
                lower(sr.canonical_name) = %(q_lower)s
                OR lower(COALESCE(sr.display_label, '')) = %(q_lower)s
                OR EXISTS (
                    SELECT 1
                    FROM regexp_split_to_table(COALESCE(sr.aliases_pipe_delimited, ''), E'\\|')
                        AS alias_value
                    WHERE lower(btrim(alias_value)) = %(q_lower)s
                )
                OR lower(sr.canonical_name) LIKE %(prefix)s
                OR lower(COALESCE(sr.display_label, '')) LIKE %(prefix)s
                OR EXISTS (
                    SELECT 1
                    FROM regexp_split_to_table(COALESCE(sr.aliases_pipe_delimited, ''), E'\\|')
                        AS alias_value
                    WHERE lower(btrim(alias_value)) LIKE %(prefix)s
                )
                OR sr.document @@ websearch_to_tsquery('simple', %(q)s)
            )
            {where_sql}
        ORDER BY
            CASE
                WHEN lower(sr.canonical_name) = %(q_lower)s THEN 1
                WHEN lower(COALESCE(sr.display_label, '')) = %(q_lower)s THEN 2
                WHEN EXISTS (
                    SELECT 1
                    FROM regexp_split_to_table(COALESCE(sr.aliases_pipe_delimited, ''), E'\\|')
                        AS alias_value
                    WHERE lower(btrim(alias_value)) = %(q_lower)s
                ) THEN 3
                WHEN
                    lower(sr.canonical_name) LIKE %(prefix)s
                    OR lower(COALESCE(sr.display_label, '')) LIKE %(prefix)s
                    OR EXISTS (
                        SELECT 1
                        FROM regexp_split_to_table(COALESCE(sr.aliases_pipe_delimited, ''), E'\\|')
                            AS alias_value
                        WHERE lower(btrim(alias_value)) LIKE %(prefix)s
                    )
                THEN 4
                ELSE 5
            END ASC,
            CASE
                WHEN sr.document @@ websearch_to_tsquery('simple', %(q)s)
                THEN ts_rank(sr.document, websearch_to_tsquery('simple', %(q)s))
                ELSE 0
            END DESC,
            sr.entity_id ASC
        LIMIT %(limit)s
        OFFSET %(offset)s;
    """

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return rows if rows is not None else []


@router.get("/search", response_model=list[SearchResultResponse])
def search_entities(
    q: str = Query(..., description="Search text."),
    entity_type: str | None = Query(default=None),
    primary_scope_game: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    conn: Connection[Any] = Depends(get_db_connection),
) -> list[SearchResultResponse]:
    """Search entities with identity-first ranking and optional filters."""
    normalized_q = q.strip()
    if not normalized_q:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=["q cannot be blank."],
        )

    normalized_entity_type, normalized_primary_scope_game = _validate_search_filters(
        entity_type=entity_type,
        primary_scope_game=primary_scope_game,
    )

    try:
        rows = _search_entities(
            conn,
            q=normalized_q,
            entity_type=normalized_entity_type,
            primary_scope_game=normalized_primary_scope_game,
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

    return [_row_to_search_result(row) for row in _sort_search_rows(rows, normalized_q)]
