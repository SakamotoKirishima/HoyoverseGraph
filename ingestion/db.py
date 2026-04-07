"""Database helpers for ingestion pipelines.

Usage:
    from ingestion.db import (
        get_connection,
        upsert_entities,
        upsert_sources,
        upsert_source_assets,
    )
    with get_connection(database_url) as conn:
        entities_summary = upsert_entities(conn, entity_rows)
        with conn.transaction():
            sources_summary = upsert_sources(conn, source_rows)
            assets_summary = upsert_source_assets(conn, asset_rows)

This module contains only PostgreSQL access logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable, Mapping

if TYPE_CHECKING:
    import psycopg


@dataclass(frozen=True)
class UpsertSummary:
    """Summary of upsert results.

    Attributes:
        inserted: Number of rows inserted.
        updated: Number of rows updated via ON CONFLICT.
    """

    inserted: int
    updated: int


def get_connection(database_url: str) -> "psycopg.Connection":
    """Open a psycopg3 connection from DATABASE_URL.

    Args:
        database_url: PostgreSQL connection URL.

    Returns:
        psycopg Connection object.
    """
    import psycopg

    return psycopg.connect(database_url)


def upsert_entities(
    conn: Any,
    rows: Iterable[Mapping[str, Any]],
) -> UpsertSummary:
    """Upsert entities rows into PostgreSQL entities table.

    Uses ON CONFLICT (entity_id) DO UPDATE and returns inserted/updated counts.

    Args:
        conn: Open psycopg connection.
        rows: Iterable of validated + normalized entity rows.

    Returns:
        UpsertSummary with inserted and updated counts.
    """
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
        ON CONFLICT (entity_id) DO UPDATE
        SET
            canonical_name = EXCLUDED.canonical_name,
            entity_type = EXCLUDED.entity_type,
            primary_scope_game = EXCLUDED.primary_scope_game,
            display_label = EXCLUDED.display_label,
            aliases_pipe_delimited = EXCLUDED.aliases_pipe_delimited,
            short_description = EXCLUDED.short_description,
            starter_status = EXCLUDED.starter_status,
            notes = EXCLUDED.notes
        RETURNING (xmax = 0) AS inserted;
    """

    inserted = 0
    updated = 0

    with conn.cursor() as cur:
        for row in rows:
            cur.execute(sql, dict(row))
            result = cur.fetchone()
            was_insert = bool(result[0]) if result else False
            if was_insert:
                inserted += 1
            else:
                updated += 1

    conn.commit()
    return UpsertSummary(inserted=inserted, updated=updated)


def upsert_sources(
    conn: Any,
    rows: Iterable[Mapping[str, Any]],
) -> UpsertSummary:
    """Upsert sources rows into PostgreSQL sources table.

    Notes:
        This function does not call commit(). Caller controls transaction.
    """
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
        ON CONFLICT (source_id) DO UPDATE
        SET
            title = EXCLUDED.title,
            url = EXCLUDED.url,
            source_type = EXCLUDED.source_type,
            source_format = EXCLUDED.source_format,
            game = EXCLUDED.game,
            scope = EXCLUDED.scope,
            reliability_tier = EXCLUDED.reliability_tier,
            language = EXCLUDED.language,
            publication_date = EXCLUDED.publication_date,
            notes = EXCLUDED.notes
        RETURNING (xmax = 0) AS inserted;
    """

    inserted = 0
    updated = 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(sql, dict(row))
            result = cur.fetchone()
            was_insert = bool(result[0]) if result else False
            if was_insert:
                inserted += 1
            else:
                updated += 1

    return UpsertSummary(inserted=inserted, updated=updated)


def upsert_source_assets(
    conn: Any,
    rows: Iterable[Mapping[str, Any]],
) -> UpsertSummary:
    """Upsert source_assets rows into PostgreSQL source_assets table.

    Notes:
        This function does not call commit(). Caller controls transaction.
    """
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
        ON CONFLICT (asset_id) DO UPDATE
        SET
            source_id = EXCLUDED.source_id,
            asset_type = EXCLUDED.asset_type,
            file_path_or_url = EXCLUDED.file_path_or_url,
            locator = EXCLUDED.locator,
            description = EXCLUDED.description,
            is_primary_evidence = EXCLUDED.is_primary_evidence,
            notes = EXCLUDED.notes
        RETURNING (xmax = 0) AS inserted;
    """

    inserted = 0
    updated = 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(sql, dict(row))
            result = cur.fetchone()
            was_insert = bool(result[0]) if result else False
            if was_insert:
                inserted += 1
            else:
                updated += 1

    return UpsertSummary(inserted=inserted, updated=updated)
