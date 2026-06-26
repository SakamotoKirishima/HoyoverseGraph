# Entity Detail API

## Endpoint

`GET /entities/{entity_id}/detail`

## Purpose

Return a consolidated entity detail payload for the Entity detail page,
including canonical metadata, related claims, deduped sources, deduped assets,
and lightweight graph context.

## Path Parameters

- `entity_id`
  - Required entity ID.
  - Must match `ENT-####`.

## Validation Behavior

- Malformed `entity_id` returns `422`.
- Missing entity returns `404`.

## Example Request

```bash
curl "http://127.0.0.1:8000/entities/ENT-0804/detail"
```

## Example Response

```json
{
  "entity": {
    "entity_id": "ENT-0804",
    "canonical_name": "Kiana Kaslana",
    "display_label": "Kiana",
    "entity_type": "character",
    "primary_scope_game": "Multi",
    "aliases": ["Kiana"],
    "short_description": "Core protagonist identity reused across multiple Honkai continuities.",
    "starter_status": "seed",
    "notes": "Editorial family anchor."
  },
  "claims": [
    {
      "claim_id": "CLM-0001",
      "subject_entity_id": "ENT-0804",
      "predicate": "identity_variant",
      "object_entity_id": "ENT-0201",
      "evidence_status": "editorial_inference",
      "confidence": 0.8,
      "source_id": "SRC-INT-0001",
      "asset_id": "AST-INT-0001",
      "locator": "Internal mapping note",
      "note": "Kiana assigned to editorial family.",
      "review_status": "draft",
      "claim_status": "active",
      "supersedes_claim_id": null,
      "contradicts_claim_id": null,
      "direction": "outgoing"
    }
  ],
  "sources": [
    {
      "source_id": "SRC-INT-0001",
      "title": "Internal Editorial Mapping",
      "url": null,
      "source_type": "internal_editorial",
      "source_format": "internal_note",
      "game": "Multi",
      "scope": "identity_mapping",
      "reliability_tier": "tier_4",
      "language": "en",
      "publication_date": null,
      "notes": null
    }
  ],
  "assets": [
    {
      "asset_id": "AST-INT-0001",
      "source_id": "SRC-INT-0001",
      "asset_type": "document",
      "file_path_or_url": null,
      "locator": "Appendix A",
      "description": "Supporting mapping extract",
      "is_primary_evidence": true,
      "notes": null
    }
  ],
  "graph_context": {
    "seed_entity_id": "ENT-0804",
    "graph_url": "/graph?seed_entity_id=ENT-0804&depth=1",
    "related_claim_count": 1,
    "related_entity_count": 1,
    "source_count": 1,
    "asset_count": 1
  }
}
```

## Notes

- `aliases` are returned as `list[str]`.
- `aliases_pipe_delimited` is not exposed.
- Related claims include `incoming` or `outgoing` direction.
- Sources and assets are deduped before returning.
- Null `source_id` and `asset_id` values are excluded from the `sources` and
  `assets` collections.
- `graph_context` provides a lightweight link into `/graph`.
