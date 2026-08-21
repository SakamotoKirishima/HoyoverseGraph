# Search API

## Endpoint

`GET /search`

## Purpose

Search for entities by name, label, alias, and supporting descriptive text.
This endpoint is entity-focused and returns lightweight, source-aware results
for the Search page.

## Query Parameters

- `q`
  - Required string query.
  - Trimmed before search.
  - Blank values return `422`.
- `entity_type`
  - Optional exact-match entity type filter.
  - Validated against the shared entity-type rules.
- `primary_scope_game`
  - Optional game filter.
  - Normalized using the shared game aliases and then matched exactly.
- `limit`
  - Optional integer.
  - Default: `20`
  - Max: `100`
- `offset`
  - Optional integer.
  - Default: `0`

## Validation Behavior

- `q` is required and must not be blank after trimming.
- Invalid `entity_type` returns `422`.
- Invalid `primary_scope_game` returns `422`.
- Invalid `limit` or `offset` returns `422`.

## Example Requests

```bash
curl "http://127.0.0.1:8000/search?q=kaslana"
```

```bash
curl "http://127.0.0.1:8000/search?q=bronya&entity_type=character"
```

```bash
curl "http://127.0.0.1:8000/search?q=raiden&primary_scope_game=Genshin%20Impact"
```

```bash
curl "http://127.0.0.1:8000/search?q=welt&limit=50&offset=100"
```

## Example Response

```json
[
  {
    "entity_id": "ENT-0804",
    "canonical_name": "Kiana Kaslana",
    "display_label": "Kiana",
    "entity_type": "character",
    "primary_scope_game": "Multi",
    "aliases": ["Kiana"],
    "short_description": "Core protagonist identity reused across multiple Honkai continuities.",
    "source_count": 2
  },
  {
    "entity_id": "ENT-0201",
    "canonical_name": "K-423",
    "display_label": "K-423",
    "entity_type": "character",
    "primary_scope_game": "Honkai Impact 3",
    "aliases": ["Kiana Clone"],
    "short_description": "Clone identity associated with Kiana in Honkai Impact 3.",
    "source_count": 1
  }
]
```

## Notes

- `aliases` are returned as `list[str]`.
- `aliases_pipe_delimited` is not exposed.
- `source_count` is included and counts distinct non-null `source_id` values from
  claims touching the entity.
