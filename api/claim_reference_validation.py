"""Shared source/asset reference validation for Claims API.

This module centralizes:
- source_id / asset_id format checks
- DB existence checks for sources and source_assets
- consistency checks ensuring an asset belongs to the selected source
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from psycopg import Connection

SRC_ID_PATTERN = re.compile(r"^SRC-[A-Z]{2,5}-\d{4}$")
AST_ID_PATTERN = re.compile(r"^AST-[A-Z]{2,5}-\d{4}$")


def validate_source_asset_id_shapes(
    source_id: str | None,
    asset_id: str | None,
    *,
    source_required: bool,
) -> list[str]:
    """Validate source_id/asset_id syntactic shape and local consistency."""
    errors: list[str] = []

    if source_required:
        if source_id is None:
            errors.append("source_id is required.")
        elif not SRC_ID_PATTERN.match(source_id):
            errors.append("source_id must match SRC-{DOMAIN}-####.")
    elif source_id is not None and not SRC_ID_PATTERN.match(source_id):
        errors.append("source_id must match SRC-{DOMAIN}-#### when provided.")

    if asset_id is not None and not AST_ID_PATTERN.match(asset_id):
        errors.append("asset_id must match AST-{DOMAIN}-#### when provided.")

    if source_required and asset_id is not None and source_id is None:
        errors.append("asset_id requires source_id.")

    return errors


def validate_source_asset_references(
    conn: Connection[Any],
    source_id: str | None,
    asset_id: str | None,
) -> list[str]:
    """Validate source/asset DB references and cross-reference consistency."""
    errors: list[str] = []

    if source_id is not None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM sources WHERE source_id = %(source_id)s LIMIT 1;",
                {"source_id": source_id},
            )
            if cur.fetchone() is None:
                errors.append(f"source_id '{source_id}' does not exist.")

    if asset_id is not None:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_id
                FROM source_assets
                WHERE asset_id = %(asset_id)s
                LIMIT 1;
                """,
                {"asset_id": asset_id},
            )
            asset_row = cur.fetchone()

        if asset_row is None:
            errors.append(f"asset_id '{asset_id}' does not exist.")
        elif source_id is not None and asset_row["source_id"] != source_id:
            errors.append(
                f"asset_id '{asset_id}' belongs to source_id '{asset_row['source_id']}', "
                f"not '{source_id}'."
            )

    return errors


def validate_source_asset_fields(
    conn: Connection[Any],
    values: Mapping[str, Any],
    *,
    source_required: bool,
) -> list[str]:
    """Validate source_id/asset_id fields end-to-end for claim create/update."""
    source_id = values.get("source_id")
    asset_id = values.get("asset_id")

    if source_id is not None and not isinstance(source_id, str):
        return ["source_id must be a string when provided."]
    if asset_id is not None and not isinstance(asset_id, str):
        return ["asset_id must be a string when provided."]

    shape_errors = validate_source_asset_id_shapes(
        source_id=source_id,
        asset_id=asset_id,
        source_required=source_required,
    )
    if shape_errors:
        return shape_errors

    return validate_source_asset_references(conn, source_id=source_id, asset_id=asset_id)
