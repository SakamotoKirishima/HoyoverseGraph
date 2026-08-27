# Source Detail API

## Status

This page defines the stable contract for the planned source-centric detail
endpoint. In this subtask, the contract and response models are defined, but
repository/database retrieval is intentionally not implemented yet.

## Endpoint

`GET /sources/{source_id}/detail`

## Purpose

Return one canonical source record together with all source assets linked to
that source, all claims supported by that source, and aggregate summary counts
for the Source Inspector / Source Detail page.

This endpoint is source-centric:

- Assets are included even when no claim currently references them.
- Claims preserve `subject -> predicate -> object` direction.
- Claims include lightweight entity summaries so the frontend does not need
  separate entity lookups just to label the relationship.

## Path Parameters

- `source_id`
  - Required source ID.
  - Must match the existing source ID format:
    `SRC-(HI3|HSR|GI|GGZ|WIKI|HL|INT|GEN)-####`

## Validation Behavior

- Malformed `source_id` returns `422`.
- Valid but nonexistent `source_id` returns `404`.
- Existing source with no linked claims or assets returns `200` with empty
  `assets` and `claims` arrays plus zeroed summary counts.

## Response Shape

```json
{
  "source": {
    "source_id": "SRC-HI3-0001",
    "title": "HI3 Main Story Chapter 1",
    "url": null,
    "source_type": "official_story",
    "source_format": "in_game_text",
    "game": "Honkai Impact 3",
    "scope": "main_story",
    "reliability_tier": "tier_1",
    "language": "en",
    "publication_date": null,
    "notes": null
  },
  "assets": [
    {
      "asset_id": "AST-HI3-0001",
      "source_id": "SRC-HI3-0001",
      "asset_type": "screenshot",
      "file_path_or_url": null,
      "locator": "Chapter 1, scene X",
      "description": "Story evidence screenshot",
      "is_primary_evidence": true,
      "notes": null
    }
  ],
  "claims": [
    {
      "claim_id": "CLM-0001",
      "subject": {
        "entity_id": "ENT-0804",
        "canonical_name": "Kiana Kaslana",
        "display_label": "Kiana",
        "entity_type": "character",
        "primary_scope_game": "Multi"
      },
      "predicate": "appears_in",
      "object": {
        "entity_id": "ENT-0001",
        "canonical_name": "Honkai Impact 3",
        "display_label": "Honkai Impact 3",
        "entity_type": "game",
        "primary_scope_game": "Honkai Impact 3"
      },
      "evidence_status": "official_confirmed",
      "confidence": 1.0,
      "asset_id": "AST-HI3-0001",
      "locator": "Chapter 1",
      "note": null,
      "review_status": "approved",
      "claim_status": "active"
    }
  ],
  "summary": {
    "claim_count": 1,
    "asset_count": 1,
    "primary_evidence_asset_count": 1,
    "related_entity_count": 2
  }
}
```

## Field Meanings

### `source`

The `source` object returns the full canonical source record.

- Nullable source fields stay `null`.
- The API must not invent fallback URLs.
- Internal DB-only fields that are not already part of the canonical source
  model must not be exposed.

### `assets`

The `assets` array contains all `source_assets` rows whose `source_id` matches
the requested source.

- Sort by `asset_id` ascending.
- Dedupe by `asset_id` if needed.
- Include assets even when no claim references them.

### `claims`

The `claims` array contains all claims whose `source_id` matches the requested
source.

- Sort by `claim_id` ascending.
- Dedupe by `claim_id` if needed.
- Preserve relationship direction as `subject -> predicate -> object`.
- Include `asset_id` when the claim points to a specific asset.
- Claims without `asset_id` must still be returned.
- Include lightweight `subject` and `object` entity summaries.

### `summary`

The `summary` object is derived from the returned collections:

- `claim_count`
  - Number of returned unique claims.
- `asset_count`
  - Number of returned unique assets.
- `primary_evidence_asset_count`
  - Count of returned assets where `is_primary_evidence` is `true`.
- `related_entity_count`
  - Number of unique `subject.entity_id` and `object.entity_id` values across
    returned claims.

## Entity Summary Model

`SourceDetailEntityRef` is the reusable lightweight entity reference shape used
by `claims[].subject` and `claims[].object`.

```json
{
  "entity_id": "ENT-0804",
  "canonical_name": "Kiana Kaslana",
  "display_label": "Kiana",
  "entity_type": "character",
  "primary_scope_game": "Multi"
}
```

Notes:

- `display_label` is additive display data.
- `display_label` does not replace `canonical_name`.

## Suggested Response Models

- `SourceDetailResponse`
- `SourceDetailSource`
- `SourceDetailAsset`
- `SourceDetailClaim`
- `SourceDetailEntityRef`
- `SourceDetailSummary`

## Example Request

```bash
curl "http://127.0.0.1:8000/sources/SRC-HI3-0001/detail"
```

## Empty-State Response

```json
{
  "source": {
    "source_id": "SRC-HI3-0001",
    "title": "HI3 Main Story Chapter 1",
    "url": null,
    "source_type": "official_story",
    "source_format": "in_game_text",
    "game": "Honkai Impact 3",
    "scope": "main_story",
    "reliability_tier": "tier_1",
    "language": "en",
    "publication_date": null,
    "notes": null
  },
  "assets": [],
  "claims": [],
  "summary": {
    "claim_count": 0,
    "asset_count": 0,
    "primary_evidence_asset_count": 0,
    "related_entity_count": 0
  }
}
```

## Relationship To Provenance Model

The contract follows the existing provenance chain:

`Claim -> SourceRecord -> SourceAsset`

For this endpoint:

- the requested `source` is the central record,
- `assets` are all source assets attached to that record,
- `claims` are all claims that cite that source,
- `asset_id` on a claim optionally narrows the evidence to one specific asset.

## Error Behavior

- `422 Unprocessable Entity`
  - Returned when `source_id` is malformed.
- `404 Not Found`
  - Returned when `source_id` is valid but no source exists.
- `200 OK`
  - Returned when the source exists, including when there are zero linked
    assets and zero linked claims.
