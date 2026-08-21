# Graph API

## Endpoint

`GET /graph`

## Purpose

Return a graph-shaped neighborhood around a seed entity for the Graph page.
Nodes represent entities and edges represent claims.

## Query Parameters

- `seed_entity_id`
  - Required entity ID.
  - Must match `ENT-####`.
- `depth`
  - Optional integer.
  - Allowed values: `1` or `2`
  - Default: `1`
- `predicate`
  - Optional exact-match claim predicate filter.
- `confidence_min`
  - Optional numeric lower bound for claim confidence.
- `evidence_status`
  - Optional exact-match claim evidence status filter.
- `limit`
  - Optional integer edge limit.
  - Default: `100`
  - Max: `500`

## Validation Behavior

- Invalid `seed_entity_id` returns `422`.
- Missing seed entity returns `404`.
- Invalid `depth` returns `422`.
- Invalid `confidence_min` outside `[0, 1]` returns `422`.
- Invalid or blank `predicate` returns `422`.
- Blank `evidence_status` returns `422`.

## Example Requests

```bash
curl "http://127.0.0.1:8000/graph?seed_entity_id=ENT-0804&depth=1"
```

```bash
curl "http://127.0.0.1:8000/graph?seed_entity_id=ENT-0804&depth=2"
```

```bash
curl "http://127.0.0.1:8000/graph?seed_entity_id=ENT-0804&depth=2&predicate=appears_in&confidence_min=0.6"
```

```bash
curl "http://127.0.0.1:8000/graph?seed_entity_id=ENT-0804&evidence_status=official_confirmed&limit=50"
```

## Example Response

```json
{
  "seed_entity_id": "ENT-0804",
  "depth": 1,
  "nodes": [
    {
      "id": "ENT-0804",
      "entity_id": "ENT-0804",
      "label": "Kiana",
      "canonical_name": "Kiana Kaslana",
      "entity_type": "character",
      "primary_scope_game": "Multi",
      "short_description": "Core protagonist identity reused across multiple Honkai continuities."
    },
    {
      "id": "ENT-0001",
      "entity_id": "ENT-0001",
      "label": "Honkai Impact 3",
      "canonical_name": "Honkai Impact 3",
      "entity_type": "game",
      "primary_scope_game": "Honkai Impact 3",
      "short_description": "Game title."
    }
  ],
  "edges": [
    {
      "id": "CLM-0001",
      "claim_id": "CLM-0001",
      "source": "ENT-0804",
      "target": "ENT-0001",
      "predicate": "appears_in",
      "confidence": 0.9,
      "evidence_status": "official_confirmed",
      "source_id": "SRC-HI3-0001",
      "asset_id": "AST-HI3-0001",
      "claim_status": "active"
    }
  ]
}
```

## Notes

- Nodes are entities.
- Edges are claims.
- Edge direction is `subject_entity_id -> object_entity_id`.
- `depth=1` returns direct neighbors.
- `depth=2` adds one extra expansion hop from the direct neighbors.
