# Honkai Multiverse Knowledge Platform — Design Document

## 1. Purpose
Build a web application that helps a researcher explore how the Honkai games intersect across characters, variants, organizations, concepts, worlds, events, and cosmology.

The platform should answer questions such as:
- Which characters appear across multiple Honkai titles?
- Which entities are counterparts, expies, reincarnations, or thematic variants?
- How do concepts like Honkai, Imaginary Tree, Sea of Quanta, Aeons, Paths, Herrschers, and Stigma systems connect across titles?
- Which relationships are canon, implied, disputed, or fan-interpreted?
- What official source supports each relationship?

This is not just a wiki clone. It is a source-backed research tool built for cross-game comparison.

---

## 2. Goals

### Primary goals
1. Create a unified data model for all major Honkai-related titles.
2. Distinguish clearly between canon facts, inferred mappings, and community interpretations.
3. Support visual exploration through knowledge graphs, node maps, relationship bubbles, timelines, and entity detail pages.
4. Make every claim traceable to one or more sources.
5. Allow gradual expansion as new games, story chapters, and lore updates release.

### Secondary goals
1. Support editorial workflows for adding and reviewing lore connections.
2. Export data for later use in Notion, Obsidian, or static datasets.
3. Provide a variant database for cross-title character comparison.
4. Support advanced filtering by game, era, world, faction, concept, and confidence level.

### Non-goals for V1
- Full reproduction of every wiki page.
- User-generated editing without moderation.
- Automated scraping of everything on day one.
- Real-time multiplayer editing.
- Complete support for every HoYoverse title outside the Honkai umbrella.

---

## 3. Scope

### In scope for initial release
- Houkai Gakuen / Guns Girl Z
- Honkai Impact 3rd
- Honkai: Star Rail
- Genshin Impact where the connection is modeled through shared cosmology, cross-title motifs, or editorially defined Imaginary Tree adjacency
- Shared cosmology concepts where they are relevant to cross-game connections
- Official sources plus clearly labeled community wiki references
- Entity pages, relationship pages, source citations, graph view, search, filters

### Optional later scope
- Manga, visual novels, trailers, developer interviews, art books
- APHO as a separate timeline layer within HI3
- Cross-series comparison to Genshin or Zenless only when explicitly tied to Honkai cosmology or expy analysis
- User accounts and personal collections

---

## 4. Core product idea
The site is a **lore research graph** with three complementary views:

### A. Graph view
Interactive knowledge graph where nodes represent entities and edges represent relationships.

Examples:
- Kiana Kaslana (Herrscher of Finality) -> instance_of -> Kiana Kaslana
- Welt Yang -> appears_in -> HI3 / HSR
- Imaginary Tree -> contains -> worlds / branches
- Anti-Entropy -> opposed_by -> Schicksal
- IX -> thematic_parallel_to -> nihilism-aligned concepts

### B. Entity dossier view
A structured profile page for each node with:
- names and aliases
- game appearances
- role summary
- variants
- linked organizations
- linked events
- source excerpts
- relationship table
- confidence labels

### C. Comparison / variant view
A side-by-side comparison tool for “same-name / same-face / same-theme” entities across titles.

Examples:
- Bronya variants across GGZ / HI3 / HSR
- Seele variants across GGZ / HI3 / HSR
- Kiana / Tuna / Kaslana lineage studies
- Otto / Luocha / Void Archives adjacency mapping

---

## 5. Design principles
1. **Source first** — every relationship should point to evidence.
2. **Separate fact from interpretation** — canon and fandom analysis must not be mixed silently.
3. **Model ambiguity explicitly** — some links are contested; store that cleanly.
4. **Progressive disclosure** — casual users can browse; deep researchers can inspect citations and edge metadata.
5. **Expandable ontology** — the schema should survive new games and lore revisions.

---

## 6. Users

### Primary user
A deep lore researcher who wants to understand cross-game continuity, variants, parallels, and cosmological overlap.

### Secondary users
- content creators making theory videos
- wiki editors and lore analysts
- fans building timelines, faction maps, and character lineage charts

### User needs
- find all counterparts of a character
- inspect source-backed evidence for a theory
- browse complex factions and cosmology visually
- filter out weak or speculative links
- export notes for later writing or video scripting

---

## 7. Information architecture

### Top-level navigation
- Home
- Explore Graph
- Characters
- Variants
- Concepts
- Factions
- Events
- Timelines
- Sources
- Methodology

### Key page types
1. **Character page**
2. **Concept page**
3. **Faction page**
4. **World / location page**
5. **Event page**
6. **Source page**
7. **Relationship page**
8. **Variant comparison page**

## Key architectural principle

This system is not a wiki.

It is a **source-backed claim graph**.

- Entities are nodes
- Claims are edges
- Sources justify claims
- Assets prove claims

The graph is a projection, not the primary storage model.

---

## 8. Data model
The system uses a **claim-first relational model**, with graph views generated dynamically.

This allows:
- precise provenance tracking
- retcon and contradiction modeling
- flexible filtering by evidence strength

### Core modeling approach

The system is **claim-first**, not edge-first.

Every relationship is stored as an atomic **claim**, with:
- subject
- predicate
- object
- source
- optional evidence (assets)
- editorial metadata
- retcon / contradiction links

The graph is derived from claims.

---

### Entity (nodes)
Fields:
- id
- canonical_name
- entity_type
- primary_scope_game
- display_label
- aliases_pipe_delimited
- short_description
- starter_status
- notes

---

### Claim (edges + metadata)
Fields:
- id
- subject_entity_id
- predicate
- object_entity_id
- evidence_status
- confidence
- source_id
- asset_id (optional)
- locator (optional)
- note
- review_status
- claim_status
- supersedes_claim_id (retcons)
- contradicts_claim_id (conflicts)

---

### SourceRecord (sources_registry)
Fields:
- id
- title
- url (optional)
- source_type
- source_format
- game
- scope
- reliability_tier
- language
- publication_date
- notes

---

### SourceAsset (evidence layer)
Fields:
- id
- source_id
- asset_type
- file_path_or_url
- locator
- description
- is_primary_evidence
- notes

### Supported relationship types

Structural:
- instance_of
- exists_in
- part_of
- occurs_in

Affiliation:
- member_of
- allied_with
- opposes

Cross-title identity:
- same_entity
- identity_variant
- archetype_parallel

Weak / interpretive:
- thematic_similarity
- shared_motif
- possible_link
- disputed_link_to
- explicitly_not_variant

Contextual:
- appears_in
- originates_from
- associated_with
- references

Narrative/meta:
- precedes (optional if used)
- supersedes (retcon)
- contradicts (conflict)

---

## Provenance model

Each claim is traceable through:

Claim → SourceRecord → SourceAsset

- SourceRecord defines origin
- SourceAsset provides proof (screenshot, timestamp, etc.)

This enables:
- verifiable claims
- auditability
- UI evidence display

## 9. Ontology rules
This is the most important modeling layer.

### Rule 1: same face does not automatically mean same identity
A visual similarity should not be stored as identity. It should use relationship types like:
- counterpart_of
- expy_of
- shares_motif_with

### Rule 2: official text outranks wiki summary
Wikis help with recall and discovery, but official text should determine canon status whenever available.

### Rule 3: store ambiguity instead of flattening it
If a connection is debated, record:
- the link type
- why it is uncertain
- which sources support it
- which sources fail to confirm it

### Rule 4: variant groups are editorial containers
A variant group is a research construct. It should not be presented as in-universe canon unless a source explicitly frames it that way.

### Rule 5: timeline and cosmology are separate layers
Chronology within one title and cosmology across titles should be modeled separately.

### Additional modeling rules

- Claims are the unit of truth. Entities do not store facts directly.
- Every claim must reference a source_id.
- asset_id is optional but recommended for precise evidence.
- character_iteration must always:
  - instance_of a base character
  - exists_in a world_realm

- Do not invent new predicates prematurely.
  Use `associated_with` + notes when needed.

- Use weakest valid relationship:
  identity_variant > archetype_parallel > thematic_similarity > shared_motif

- Use explicitly_not_variant to prevent false clustering.

- Retcons are modeled using supersedes_claim_id.
- Contradictions are modeled using contradicts_claim_id.

- Narrative intent (early plotlines) should be expressed in notes,
  not by introducing unstable predicates.

---

## 10. Source strategy

### Source tiers

#### Tier 1 — official, highest priority
- official game websites
- in-game databanks / archives / glossaries
- official main story chapter text
- official character profiles and faction pages
- official trailers and promotional lore pages
- developer posts or official interviews

#### Tier 2 — official companion material
- officially released manga or companion media
- HoYoLAB posts when used for official explanatory material
- official social posts that contain lore-relevant details
- officially published patch notes that add lore entries, databank records, readable items, or archive text

#### Tier 3 — structured community references
- Fandom / Miraheze / independent wiki projects
- fan-maintained timelines
- transcription repositories for story dialogue
- lore essays and theory compendia

#### Tier 4 — internal editorial research
- manually curated notes
- normalized entity spreadsheets
- approved editorial relationship mappings

### Recommended starting coverage order
1. main story content for each included game
2. in-game databanks, glossaries, and profile pages
3. official companion media such as manga
4. permanent world-building side text and readable archives
5. limited-time events and event-only lore
6. trailers, promos, interviews, and supplemental community references

### Important clarification

A source does not need a public URL.

For in-game content:
- source_format = in_game_text
- url may be empty
- supporting evidence is stored in source_assets (screenshots)

Videos (YouTube/Twitch) are Tier 3 fallback sources only.

### Source ingestion policy
For each source, capture:
- URL
- source type
- official vs community
- page title
- date accessed
- game association
- story scope (main story / manga / event / databank / promo)
- extracted claims
- quoted text or summary

### Important implementation rule
Wikis are a strong starting layer for discovery and entity recall, especially for older or fragmented material, but they should not be the final authority on canon classification. The recommended workflow is:
1. use wikis to build the first pass of entities, aliases, timelines, and candidate links
2. attach at least one stronger confirming source whenever possible
3. keep claims publishable even when only wiki-backed, but label them clearly as provisional or community-supported until verified
4. preserve dissent and ambiguity rather than forcing a single interpretation

### Search strategy
For V1, PostgreSQL full-text search is acceptable if the dataset is small and curated. However, Elasticsearch is a reasonable choice if the product is expected to support:
- fuzzy alias matching across localized character names
- weighted relevance across entities, relationships, and citations
- typo tolerance and synonym dictionaries
- faceted filtering at scale
- hybrid ranking across exact names, aliases, source excerpts, and editorial notes

Recommendation:
- V1: PostgreSQL full-text if you want minimum operational overhead
- V1.5 or V2: Elasticsearch once source volume and citation text become substantial

If you already expect thousands of entities, aliases, source excerpts, and searchable claims early on, starting with Elasticsearch is defensible.

## 11. Functional requirements

### 11.1 Search
- full-text search across entities, aliases, and source excerpts
- autocomplete for names and concepts
- filters by game, entity type, canon status, confidence, faction, source tier

### 11.2 Graph exploration
- zoom / pan / drag nodes
- expand neighbors on click
- filter edge types
- color nodes by game or entity type
- toggle source confidence layer
- pin nodes and save graph views

### 11.3 Entity pages
- summary card
- aliases and naming history
- appearances by game
- relationship matrix
- source-backed evidence panel
- spoiler toggle
- linked timelines

### 11.4 Variant explorer
- view all entities in a variant group
- compare attributes: design motifs, role, affiliation, powers, themes, status
- show what is explicit vs editorial inference

### 11.5 Timeline view
- title-specific chronology
- cross-title concept chronology
- event clusters and causality links

### 11.6 Source inspector
- browse all citations tied to a node or edge
- open source page record
- see exact claim provenance

### 11.7 Admin / editorial workflow
- ingest source
- extract candidate entities and claims
- review / approve / reject
- merge duplicates
- create or revise relationships
- attach citations

---

## 12. Non-functional requirements
- responsive web app
- accessible graph interactions where feasible
- fast search under large lore datasets
- strong provenance tracking
- easy schema evolution
- version history for editorial changes

---

## 13. Recommended architecture

### Frontend
- **Next.js** for app shell, routing, SSR, and SEO
- **TypeScript** throughout
- **Tailwind CSS** for UI system
- **React Flow**, **Cytoscape.js**, or **Sigma.js** for graph rendering
- **TanStack Query** for client data fetching and caching

### Backend
Two valid options:

#### Option A — practical hybrid stack
- Next.js API routes or separate **FastAPI** service
- **PostgreSQL** for structured metadata
- **Neo4j** for graph queries
- **OpenSearch** or PostgreSQL full-text for search

#### Option B — simpler V1 stack
- PostgreSQL only, with relationship tables
- graph view generated from relational queries
- later migrate to Neo4j if graph complexity grows

Recommendation: start with **PostgreSQL + relationship tables** for V1 unless you already know you need advanced graph traversal queries. Add Neo4j in V2.

### Data ingestion pipeline
- Python ingestion workers
- HTML parsing and source normalization
- manual review queue
- optional LLM-assisted extraction with human approval

### Storage layers
- relational DB for entities, relationships, citations
- object storage for source snapshots and images
- cache layer with Redis if needed later

---

## 14. Data ingestion pipeline design

### Stage 1: source registry
A curated list of source URLs and source types.

### Stage 2: fetch and snapshot
Store HTML/text snapshot with access date so you can reproduce the source later.

### Stage 3: parse
Extract:
- title
- headings
- infobox-like fields
- paragraphs
- tables
- links

### Stage 4: claim extraction
Initial options:
- regex / rules for structured pages
- manual annotation UI
- optional LLM extraction for candidate triples

Example extracted triples:
- Seele Vollerei -> appears_in -> Honkai Impact 3rd
- Bronya Rand -> counterpart_of -> Bronya Zaychik
- Sea of Quanta -> thematic_parallel_to -> fragmented world structures

### Stage 5: editorial review
Human reviewer confirms:
- node identity
- relationship type
- canon status
- confidence
- supporting citations

### Stage 6: publish
Approved data is indexed for graph and search.

---

## 15. LLM usage policy
Use LLMs only as assistants, not as truth sources.

### Safe uses
- suggest candidate entities from source text
- suggest candidate relationships
- summarize long official text for internal review
- deduplicate aliases and naming variants

### Unsafe uses
- inventing relationships without sources
- deciding canon status autonomously
- collapsing ambiguous entities into a single identity without review

### Recommendation
Every LLM-generated claim must remain unpublished until a human accepts it.

---

## 16. UI / UX design

### Home page
- short explanation of platform purpose
- featured graph: “How the Honkai titles intersect”
- entry points: characters, concepts, variants, cosmology

### Graph view UI
Left sidebar:
- search
- filters
- legend
- saved views

Center:
- interactive graph canvas

Right drawer:
- selected node details
- relationship evidence
- quick expand buttons

### Entity page UI sections
1. header with name, aliases, game tags
2. summary
3. relationship overview
4. appearances
5. sources and citations
6. timeline placement
7. editorial notes / ambiguity callouts

### Variant comparison UI
- table layout with expandable cards
- motif tags
- role tags
- evidence panel beneath each comparison row

### Visual language
- node colors by entity type
- border or glow by source confidence
- edge styles by canon status
  - solid = explicit canon
  - dashed = implied
  - dotted = community theory

---

## 17. Example user journeys

### Journey 1: find all Bronya variants
1. user searches Bronya
2. sees variant group results
3. opens comparison page
4. filters to official-only evidence
5. inspects each linked citation

### Journey 2: understand cosmology overlap
1. user opens concept “Imaginary Tree”
2. graph expands to Sea of Quanta, worlds, branches, Aeons, related metaphysical systems
3. user filters by HI3 and HSR only
4. user opens source excerpts to verify the mapping

### Journey 3: build video notes
1. user selects nodes for Kiana, Sirin, Herrscher of Finality, Cocoon, Nanook, Akivili, Imaginary Tree
2. pins graph
3. exports saved view and citations

---

## 18. Suggested V1 schema examples

### Example node
**Entity**
- canonical_name: Bronya Zaychik
- entity_type: character
- primary_game: Honkai Impact 3rd

### Example relationships
- Bronya Zaychik -> identity_variant -> Bronya Rand
- Yae Sakura -> archetype_parallel -> Yae Miko
- Ruan Mei -> explicitly_not_variant -> Raiden Mei
- Kiana Kaslana (Herrscher of Finality) -> instance_of -> Kiana Kaslana
- Kiana Kaslana (St. Freya) -> exists_in -> HI3 Main Story Continuity
- Anti-Entropy -> opposes -> Schicksal
- Acheron -> thematic_similarity -> Raiden Ei

### Example citations
- official profile text
- in-game databank entry
- wiki summary used only as supplemental reference

---

## 19. Taxonomy proposal

### Entity types
- character
- organization
- concept
- world
- location
- event
- artifact
- power_system
- title_or_rank
- timeline
- source_record

### Tag families
- game
- era
- faction
- species
- motif
- theme
- cosmology
- spoiler_tier

### Motif tags for variant analysis
- moon
- flame
- void
- rebirth
- orphanage
- authority
- memory
- sacrifice
- parallel_self
- apocalypse

---

## 20. Editorial methodology page
This page should exist publicly so users understand your standards.

It should explain:
- how official and community sources are weighted
- what “counterpart”, “variant”, “expy”, and “thematic parallel” mean in this database
- why some links are intentionally labeled uncertain
- how new data is reviewed

This is critical because lore communities often dispute terminology.

---

## 21. Security and legal considerations
- respect source site terms of use
- avoid redistributing large copyrighted text blocks
- store short excerpts for citation, not full commercial text dumps unless permitted
- rate limit or cache fetches
- attribute community wikis properly
- keep internal source snapshots private if needed

---

## 22. MVP definition

### V1 features
- curated source registry
- entity database for major recurring characters, concepts, and factions
- graph explorer
- entity detail pages
- variant comparison pages
- citations and source inspector
- admin interface for manual curation

### V1 content focus
Start narrow:
- major recurring characters: Kiana, Mei, Bronya, Seele, Welt, Otto, Sirin, Theresa
- major concepts: Honkai, Herrscher, Imaginary Tree, Sea of Quanta, Stigma, Aeons, Paths
- major factions: Schicksal, Anti-Entropy, World Serpent, Astral Express, IPC, Stellaron Hunters where relevant

This gives enough value without requiring complete encyclopedic coverage.

---

## 23. Phased roadmap

### Phase 0 — completed
- ontology defined
- relationship taxonomy finalized
- source + evidence system designed
- editorial rules defined
- seed dataset created (entities + claims)
- retcon and contradiction modeling validated

### Phase 1 — MVP build
- relational schema (PostgreSQL)
- Excel → DB ingestion pipeline
- entity CRUD APIs
- claim CRUD APIs
- source + asset CRUD
- graph page (derived from claims)
- search page
- entity detail pages

### Phase 2 — ingestion tooling
- fetcher
- parser
- claim extraction queue
- editorial review dashboard

### Phase 3 — advanced exploration
- saved graphs
- export to markdown / CSV / JSON
- richer timelines
- graph analytics and clustering

### Phase 4 — community layer
- user accounts
- personal collections
- suggestion queue
- moderated community submissions

---

## 24. Recommended tech choices

### Preferred stack for a solo or small-team project
- Frontend: Next.js + TypeScript + Tailwind
- Backend: FastAPI or Next.js server actions
- Database: PostgreSQL
- Search: PostgreSQL full-text initially
- Graph rendering: Cytoscape.js
- Ingestion: Python scripts
- Auth: optional in V1
- Hosting: Vercel for frontend, Railway / Render / Fly.io / Supabase for backend and DB

### Why this stack
- fast iteration
- easy deployment
- strong TypeScript + Python combination
- good enough for curated datasets before graph scale becomes massive

---

## 25. Example API design

### Public endpoints
- `GET /api/search?q=`
- `GET /api/entities/:slug`
- `GET /api/entities/:id/relationships`
- `GET /api/variant-groups/:slug`
- `GET /api/graph?seed=...&depth=...`
- `GET /api/sources/:id`

### Admin endpoints
- `POST /api/admin/sources`
- `POST /api/admin/claims/extract`
- `POST /api/admin/relationships`
- `PATCH /api/admin/claims/:id/review`

---

## 26. Example database decisions

### Why not only use wiki scraping?
Because you need trust, provenance, and a clean separation between:
- explicit canon
- editorial inference
- fan interpretation

### Why not only use a graph DB?
A graph DB is useful, but V1 complexity may not justify it if the dataset is curated and moderate in size.

### Why relational first?
You will spend more time defining ontology and reviewing claims than running exotic traversal queries in the first version.

---

## 27. Success metrics
- user can find a character or concept in under 10 seconds
- each important relationship has at least one visible citation
- graph view remains understandable after filter usage
- editorial workflow can add a new entity and link it in under 5 minutes
- variant pages make ambiguous relationships easier, not more confusing

---

## 28. Risks

### Risk 1: ontology collapse
Different kinds of “same-ness” get mixed together.
**Mitigation:** strict relationship taxonomy and methodology page.

### Risk 2: source drift
Wikis change, official pages move, lore updates invalidate assumptions.
**Mitigation:** snapshots, source dates, and revision history.

### Risk 3: over-automation
LLM extraction creates false links.
**Mitigation:** human review gate.

### Risk 4: scope explosion
Trying to ingest every page across all media too early.
**Mitigation:** curated MVP with seed entities only.

---

## 29. Open questions
- Will manga and side media be first-class sources in V1 or V2?
- Will APHO be modeled as separate timeline nodes or as part of HI3 chronology?
- How will spoilers be tiered across games and patch versions?
- Do you want private research notes attached to entities?
- Do you want export directly into Notion or Obsidian later?

---

## 30. Recommended immediate next steps
1. finalize ontology and relationship taxonomy
2. choose 25 to 40 seed entities
3. build a spreadsheet or JSON seed dataset
4. implement relational schema and simple admin CRUD
5. build graph and entity views
6. ingest official sources first, wiki sources second
7. add editorial review flow before any automation

---

## 31. Suggested seed dataset

### Characters
- Kiana Kaslana
- Raiden Mei
- Bronya Zaychik
- Seele Vollerei
- Welt Yang
- Otto Apocalypse
- Theresa Apocalypse
- Sirin
- Kevin Kaslana
- Fu Hua
- Bronya Rand
- Acheron / Raiden Bosenmori Mei
- Luocha

### Concepts
- Honkai
- Herrscher
- Imaginary Tree
- Sea of Quanta
- Cocoon of Finality
- Stellaron
- Aeon
- Path
- Stigmata

### Factions
- Schicksal
- Anti-Entropy
- World Serpent
- Astral Express
- Interastral Peace Corporation
- Stellaron Hunters

---

## 32. Final recommendation
Start with a **curated, citation-first research platform** rather than a fully automated lore crawler.

The real product value is not just storing lore. It is:
- defining a clean ontology for intersections
- separating canon from interpretation
- making cross-title comparison visually legible
- backing every link with evidence

That combination will make the platform substantially more useful than a normal wiki.

