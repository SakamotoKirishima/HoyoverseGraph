-- Initial schema for Hoyoverse knowledge graph (Neon/PostgreSQL compatible)
-- Step 1: core entities table only.

CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    primary_scope_game TEXT,
    display_label TEXT,
    aliases_pipe_delimited TEXT,
    short_description TEXT,
    starter_status TEXT,
    notes TEXT,
    CONSTRAINT uq_entities_canonical_name_entity_type
        UNIQUE (canonical_name, entity_type)
);

-- Lookup and filtering indexes.
CREATE INDEX IF NOT EXISTS idx_entities_canonical_name
    ON entities (canonical_name);

CREATE INDEX IF NOT EXISTS idx_entities_entity_type
    ON entities (entity_type);

CREATE INDEX IF NOT EXISTS idx_entities_primary_scope_game
    ON entities (primary_scope_game);

-- Step 2: claims table.
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    subject_entity_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_entity_id TEXT NOT NULL,
    evidence_status TEXT,
    confidence NUMERIC,
    source_id TEXT,
    asset_id TEXT,
    locator TEXT,
    note TEXT,
    review_status TEXT,
    claim_status TEXT,
    supersedes_claim_id TEXT,
    contradicts_claim_id TEXT,
    CONSTRAINT fk_claims_subject_entity
        FOREIGN KEY (subject_entity_id) REFERENCES entities (entity_id),
    CONSTRAINT fk_claims_object_entity
        FOREIGN KEY (object_entity_id) REFERENCES entities (entity_id),
    CONSTRAINT fk_claims_supersedes
        FOREIGN KEY (supersedes_claim_id) REFERENCES claims (claim_id),
    CONSTRAINT fk_claims_contradicts
        FOREIGN KEY (contradicts_claim_id) REFERENCES claims (claim_id),
    CONSTRAINT uq_claims_spo_source
        UNIQUE (subject_entity_id, predicate, object_entity_id, source_id)
);

-- Query-path indexes for graph traversal and evidence filtering.
CREATE INDEX IF NOT EXISTS idx_claims_subject_entity_id
    ON claims (subject_entity_id);

CREATE INDEX IF NOT EXISTS idx_claims_object_entity_id
    ON claims (object_entity_id);

CREATE INDEX IF NOT EXISTS idx_claims_predicate
    ON claims (predicate);

CREATE INDEX IF NOT EXISTS idx_claims_evidence_status
    ON claims (evidence_status);

CREATE INDEX IF NOT EXISTS idx_claims_confidence
    ON claims (confidence);

CREATE INDEX IF NOT EXISTS idx_claims_source_id
    ON claims (source_id);

-- Step 3: sources table (sources_registry).
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    -- Nullable: in-game text/dialog entries may not have a public web URL.
    url TEXT,
    source_type TEXT NOT NULL,
    -- Kept separate from source_type so medium/format can be queried independently
    -- (for example: official + patch_notes vs official + trailer).
    source_format TEXT NOT NULL,
    game TEXT,
    scope TEXT,
    reliability_tier TEXT,
    language TEXT,
    publication_date DATE,
    notes TEXT,
    CONSTRAINT uq_sources_dedupe_fingerprint
        UNIQUE (title, source_type, source_format, game, scope, language, publication_date)
);

CREATE INDEX IF NOT EXISTS idx_sources_title
    ON sources (title);

CREATE INDEX IF NOT EXISTS idx_sources_source_type
    ON sources (source_type);

CREATE INDEX IF NOT EXISTS idx_sources_source_format
    ON sources (source_format);

CREATE INDEX IF NOT EXISTS idx_sources_game
    ON sources (game);

CREATE INDEX IF NOT EXISTS idx_sources_scope
    ON sources (scope);

CREATE INDEX IF NOT EXISTS idx_sources_reliability_tier
    ON sources (reliability_tier);

CREATE INDEX IF NOT EXISTS idx_sources_publication_date
    ON sources (publication_date);

-- Link claims to sources once sources exists in schema.
ALTER TABLE claims
    ADD CONSTRAINT fk_claims_source
    FOREIGN KEY (source_id) REFERENCES sources (source_id);

-- Step 4: source_assets table.
-- source_assets stores evidence artifacts/attachments that support a source
-- record, while sources stores the source record metadata itself.
CREATE TABLE IF NOT EXISTS source_assets (
    asset_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    -- Nullable: some evidence is represented by locator text only, or the asset
    -- may be attached later after initial claim/source ingestion.
    file_path_or_url TEXT,
    locator TEXT,
    description TEXT,
    is_primary_evidence BOOLEAN,
    notes TEXT,
    CONSTRAINT fk_source_assets_source
        FOREIGN KEY (source_id) REFERENCES sources (source_id),
    CONSTRAINT uq_source_assets_dedupe_fingerprint
        UNIQUE (source_id, asset_type, file_path_or_url, locator)
);

CREATE INDEX IF NOT EXISTS idx_source_assets_source_id
    ON source_assets (source_id);

CREATE INDEX IF NOT EXISTS idx_source_assets_asset_type
    ON source_assets (asset_type);

CREATE INDEX IF NOT EXISTS idx_source_assets_is_primary_evidence
    ON source_assets (is_primary_evidence);

-- Link claims to source_assets once source_assets exists in schema.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_claims_asset'
    ) THEN
        ALTER TABLE claims
            ADD CONSTRAINT fk_claims_asset
            FOREIGN KEY (asset_id) REFERENCES source_assets (asset_id);
    END IF;
END $$;
