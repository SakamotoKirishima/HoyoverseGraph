# Search Contract

This document defines the initial backend search contract for the HoYoverse Knowledge Graph search page. It describes what entity fields are searchable, what search results should return, which filters are supported, and how ranking should behave before the API endpoint is implemented.

## Scope

Initial search is entity-focused.

- Search targets `entities`
- Search behavior is source-aware where practical
- No database schema changes are required for this step
- No API or UI implementation is included in this step

## Searchable Fields

The initial search surface for entities is:

- `canonical_name`
- `display_label`
- `aliases_pipe_delimited`
- `short_description`
- `notes`

### Field Intent

- `canonical_name`: primary entity identity and the strongest ranking signal
- `display_label`: user-facing label that may differ slightly from canonical naming. If `display_label` is null or empty, search behavior should fall back to `canonical_name`.
- `aliases_pipe_delimited`: alternate names, titles, and common lookup variants
- `short_description`: short explanatory text for broader discovery
- `notes`: lower-priority internal/editorial text that may still help recall

## Result Fields

Initial search results should return these entity fields:

- `entity_id`
- `canonical_name`
- `display_label`
- `entity_type`
- `primary_scope_game`
- `aliases`
- `short_description`

Planned optional fields:

- `matched_fields`
- `source_summary`
- `source_count`
- `search_score`

### Optional Result Field Notes

- `search_score` is an implementation detail and may be omitted from the UI.
- It is primarily intended for debugging, ranking analysis, and future search tuning.
- Higher values indicate stronger matches.
- Exact identity matches should receive higher scores than descriptive-text matches.

Example:

```json
{
  "entity_id": "ENT-0807",
  "canonical_name": "Raiden Shogun",
  "search_score": 0.91
}
```

### Result Field Notes

- `aliases` should be returned as `list[str]`
- `aliases_pipe_delimited` should not be exposed directly in API responses
- `matched_fields` can be added later to explain why a result matched
- `source_summary` can be added later as a lightweight provenance-oriented addition
- `source_count` is the preferred first step for source awareness

## Filters

Initial filter support:

- `entity_type`
- `primary_scope_game`

### Filter Behavior

- `entity_type` should be an exact filter against the canonical stored value.
- `primary_scope_game` should use the existing canonical game normalization rules already used elsewhere in the backend.
- Multiple filters are combined using AND semantics.
- Omitted filters are ignored.

Example:

```text
entity_type=character
primary_scope_game=Honkai Impact 3
```

Returns only entities that satisfy both conditions.

Example:

```text
q=bronya
entity_type=character
```

Returns only character entities matching "bronya".

Example:

```text
q=bronya
```

Returns matching entities from all entity types.

## Query Parameters

The initial search endpoint should support the following query parameters:

| Parameter | Type | Required | Default | Description |
|------------|------|----------|---------|-------------|
| `q` | string | yes | — | Search query |
| `entity_type` | string | no | none | Filter by entity type |
| `primary_scope_game` | string | no | none | Filter by game |
| `limit` | integer | no | 20 | Maximum number of results |
| `offset` | integer | no | 0 | Pagination offset |

### Query Parameter Notes

- `q` is required.
- Filters are optional.
- `limit` should have a reasonable upper bound (for example 100).
- Pagination uses offset-based pagination for the initial version.
- Future versions may add cursor-based pagination.

Example:

```text
GET /search?q=kaslana

GET /search?q=bronya&entity_type=character

GET /search?q=raiden&primary_scope_game=Genshin Impact

GET /search?q=welt&limit=50&offset=100
```

## Ranking Priority

Search ranking should prefer stronger identity matches before broader text recall.

Priority order:

1. exact `canonical_name` match
2. exact `display_label` match
3. exact alias match
4. prefix match on name or alias
5. full-text match in `short_description` or `notes`

### Ranking Notes

- Exact identity matches should outrank descriptive-text matches
- Alias hits should be strong, but still rank below exact canonical/display matches
- Description and note matches are useful for discovery, but should be lower-confidence ranking signals
- Entities without a `display_label` should behave as though `display_label = canonical_name` for ranking purposes.

## Alias Behavior

Aliases are currently stored in the database as pipe-delimited text in `aliases_pipe_delimited`.

Contract:

- storage remains pipe-delimited in the database
- API responses should return aliases as `list[str]`
- alias matching should be case-insensitive
- exact alias matches should rank above prefix alias matches

Example:

- DB value: `Ei|Raiden Ei|Electro Archon`
- API value: `["Ei", "Raiden Ei", "Electro Archon"]`

## Source-Aware Results

Search results should be source-aware, but the first version can stay lightweight.

Initial acceptable options:

- `source_count: int`

`has_sources` should be derived by clients as:

```python
has_sources = source_count > 0
```

### Source Count Notes

- `source_count` is preferred over `has_sources`.
- It provides more information while still allowing clients to derive a boolean if desired.
- `source_count = 0` indicates no source-backed graph coverage.
- The first version should avoid heavy nested provenance payloads.

Later expansion:

- lightweight `source_summary`
- lightweight provenance snippets tied to claims or sources

### Source-Aware Guidance

- Source awareness should help users distinguish entities that have evidence-backed graph coverage
- The first version should avoid heavy nested provenance payloads
- Source summaries can be added later once the search endpoint shape is stable

## Proposed Initial Search Response Shape

Illustrative example:

```json
{
  "entity_id": "ENT-0121",
  "canonical_name": "Raiden Shogun",
  "display_label": "Raiden Shogun",
  "entity_type": "character",
  "primary_scope_game": "Genshin Impact",
  "aliases": ["Ei", "Raiden Ei"],
  "short_description": "Electro Archon of Inazuma.",
  "source_count": 4
}
```

Possible later expansion:

```json
{
  "entity_id": "ENT-0121",
  "canonical_name": "Raiden Shogun",
  "display_label": "Raiden Shogun",
  "entity_type": "character",
  "primary_scope_game": "Genshin Impact",
  "aliases": ["Ei", "Raiden Ei"],
  "short_description": "Electro Archon of Inazuma.",
  "matched_fields": ["canonical_name", "aliases"],
  "source_summary": {
    "source_count": 4
  }
}
```

## Non-Goals For This Step

- no search endpoint implementation yet
- no database schema changes yet
- no frontend/Next.js search page implementation yet
- no persisted search index design yet

## Decision Summary

- Search is entity-first
- Ranking is identity-first
- Aliases are first-class search inputs
- Results should be API-friendly and avoid exposing raw pipe-delimited storage
- Source awareness should start lightweight and expand later
