"""Unit tests for claim validation/helper modules."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from api import claim_reference_validation as crv
from api import claim_relationship_validation as clv
from api import claim_validation as cv
from api import claims


class _FakeCursor:
    def __init__(self, conn: "_FakeConn"):
        self._conn = conn
        self._last_result: dict[str, Any] | None = None

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params: dict[str, Any]) -> None:
        self._last_result = self._conn.dispatch(sql, params)

    def fetchone(self) -> dict[str, Any] | None:
        return self._last_result


class _FakeConn:
    def __init__(
        self,
        *,
        sources: set[str] | None = None,
        assets: dict[str, str] | None = None,
        claim_ids: set[str] | None = None,
    ):
        self.sources = sources or set()
        self.assets = assets or {}
        self.claim_ids = claim_ids or set()

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)

    def dispatch(self, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
        normalized_sql = " ".join(sql.split()).lower()
        if "from sources" in normalized_sql:
            return {"ok": 1} if params["source_id"] in self.sources else None
        if "from source_assets" in normalized_sql:
            asset_source_id = self.assets.get(params["asset_id"])
            return {"source_id": asset_source_id} if asset_source_id is not None else None
        if "from claims" in normalized_sql:
            return {"ok": 1} if params["claim_id"] in self.claim_ids else None
        raise AssertionError(f"Unexpected SQL in fake connection: {sql}")


def test_predicate_validation_valid_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cv, "get_allowed_predicates", lambda: {"appears_in"})
    assert cv.validate_predicate_usage("appears_in") == []


def test_predicate_validation_invalid_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cv, "get_allowed_predicates", lambda: {"appears_in"})
    errors = cv.validate_predicate_usage("invalid_predicate")
    assert any("not in relationship_types" in err for err in errors)


def test_predicate_validation_blank_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cv, "get_allowed_predicates", lambda: {"appears_in"})
    errors = cv.validate_predicate_usage("")
    assert any("not in relationship_types" in err for err in errors)


def test_source_asset_shape_valid_source_only_passes() -> None:
    assert crv.validate_source_asset_id_shapes("SRC-HSR-0001", None, source_required=True) == []


def test_source_asset_shape_valid_asset_only_passes_when_source_not_required() -> None:
    errors = crv.validate_source_asset_id_shapes(None, "AST-HSR-0001", source_required=False)
    assert errors == []


def test_source_asset_shape_malformed_source_fails() -> None:
    errors = crv.validate_source_asset_id_shapes("SRC-001", None, source_required=True)
    assert "source_id must match SRC-{DOMAIN}-####." in errors


def test_source_asset_shape_malformed_asset_fails() -> None:
    errors = crv.validate_source_asset_id_shapes("SRC-HSR-0001", "AST-01", source_required=True)
    assert "asset_id must match AST-{DOMAIN}-#### when provided." in errors


def test_source_asset_references_matching_source_asset_passes() -> None:
    conn = _FakeConn(sources={"SRC-HSR-0001"}, assets={"AST-HSR-0001": "SRC-HSR-0001"})
    errors = crv.validate_source_asset_references(conn, "SRC-HSR-0001", "AST-HSR-0001")
    assert errors == []


def test_source_asset_references_mismatch_fails() -> None:
    conn = _FakeConn(sources={"SRC-HSR-0001"}, assets={"AST-HSR-0001": "SRC-GI-0002"})
    errors = crv.validate_source_asset_references(conn, "SRC-HSR-0001", "AST-HSR-0001")
    assert any("belongs to source_id" in err for err in errors)


def test_source_asset_references_nonexistent_source_fails() -> None:
    conn = _FakeConn(sources=set(), assets={})
    errors = crv.validate_source_asset_references(conn, "SRC-HSR-0001", None)
    assert "source_id 'SRC-HSR-0001' does not exist." in errors


def test_source_asset_references_nonexistent_asset_fails() -> None:
    conn = _FakeConn(sources={"SRC-HSR-0001"}, assets={})
    errors = crv.validate_source_asset_references(conn, "SRC-HSR-0001", "AST-HSR-0001")
    assert "asset_id 'AST-HSR-0001' does not exist." in errors


def test_claim_link_shapes_valid_both_pass() -> None:
    errors = clv.validate_claim_link_id_shapes("CLM-0001", "CLM-0002")
    assert errors == []


def test_claim_link_shapes_malformed_fails() -> None:
    errors = clv.validate_claim_link_id_shapes("BAD-ID", None)
    assert "supersedes_claim_id must match CLM-#### when provided." in errors


def test_claim_link_shapes_self_reference_fails() -> None:
    errors = clv.validate_claim_link_id_shapes("CLM-0005", None, current_claim_id="CLM-0005")
    assert any("cannot supersede itself" in err for err in errors)


def test_claim_link_references_nonexistent_supersedes_fails() -> None:
    conn = _FakeConn(claim_ids={"CLM-0002"})
    errors = clv.validate_claim_link_references(conn, "CLM-0001", None)
    assert "supersedes_claim_id 'CLM-0001' does not exist." in errors


def test_claim_link_references_nonexistent_contradicts_fails() -> None:
    conn = _FakeConn(claim_ids={"CLM-0001"})
    errors = clv.validate_claim_link_references(conn, None, "CLM-9999")
    assert "contradicts_claim_id 'CLM-9999' does not exist." in errors


def test_confidence_null_allowed() -> None:
    req = claims.ClaimCreateRequest(
        subject_entity_id="ENT-0001",
        predicate="appears_in",
        object_entity_id="ENT-0002",
        source_id="SRC-HSR-0001",
        confidence=None,
    )
    assert req.confidence is None


def test_confidence_in_range_passes() -> None:
    req = claims.ClaimCreateRequest(
        subject_entity_id="ENT-0001",
        predicate="appears_in",
        object_entity_id="ENT-0002",
        source_id="SRC-HSR-0001",
        confidence=1.0,
    )
    assert req.confidence == 1.0


def test_confidence_negative_fails() -> None:
    with pytest.raises(ValidationError):
        claims.ClaimCreateRequest(
            subject_entity_id="ENT-0001",
            predicate="appears_in",
            object_entity_id="ENT-0002",
            source_id="SRC-HSR-0001",
            confidence=-0.1,
        )


def test_confidence_above_one_fails() -> None:
    with pytest.raises(ValidationError):
        claims.ClaimCreateRequest(
            subject_entity_id="ENT-0001",
            predicate="appears_in",
            object_entity_id="ENT-0002",
            source_id="SRC-HSR-0001",
            confidence=1.1,
        )


def test_filter_confidence_range_valid_passes() -> None:
    assert claims._validate_confidence_bounds(0.2, 0.8) == []


def test_filter_confidence_min_greater_than_max_fails() -> None:
    errors = claims._validate_confidence_bounds(0.9, 0.1)
    assert "confidence_min cannot be greater than confidence_max." in errors
