"""Shared validation for claim-to-claim relationship fields.

This module centralizes validation for:
- supersedes_claim_id
- contradicts_claim_id

It is used by claims create/update flows for consistent shape and reference
integrity checks.
"""

from __future__ import annotations

import re
from typing import Any

from psycopg import Connection

CLM_ID_PATTERN = re.compile(r"^CLM-\d{4}$")


def validate_claim_link_id_shapes(
    supersedes_claim_id: str | None,
    contradicts_claim_id: str | None,
    *,
    current_claim_id: str | None = None,
) -> list[str]:
    """Validate shape and self-reference rules for claim relationship IDs."""
    errors: list[str] = []

    if supersedes_claim_id is not None:
        if not CLM_ID_PATTERN.match(supersedes_claim_id):
            errors.append("supersedes_claim_id must match CLM-#### when provided.")
        elif current_claim_id is not None and supersedes_claim_id == current_claim_id:
            errors.append(f"A claim cannot supersede itself ('{current_claim_id}').")

    if contradicts_claim_id is not None:
        if not CLM_ID_PATTERN.match(contradicts_claim_id):
            errors.append("contradicts_claim_id must match CLM-#### when provided.")
        elif current_claim_id is not None and contradicts_claim_id == current_claim_id:
            errors.append(f"A claim cannot contradict itself ('{current_claim_id}').")

    return errors


def validate_claim_link_references(
    conn: Connection[Any],
    supersedes_claim_id: str | None,
    contradicts_claim_id: str | None,
) -> list[str]:
    """Validate that referenced claims exist when provided."""
    errors: list[str] = []

    if supersedes_claim_id is not None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM claims WHERE claim_id = %(claim_id)s LIMIT 1;",
                {"claim_id": supersedes_claim_id},
            )
            if cur.fetchone() is None:
                errors.append(f"supersedes_claim_id '{supersedes_claim_id}' does not exist.")

    if contradicts_claim_id is not None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM claims WHERE claim_id = %(claim_id)s LIMIT 1;",
                {"claim_id": contradicts_claim_id},
            )
            if cur.fetchone() is None:
                errors.append(f"contradicts_claim_id '{contradicts_claim_id}' does not exist.")

    return errors
