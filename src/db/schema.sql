-- mysynapse PostgreSQL schema (idempotent — safe to run on every startup)

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    doc_type        TEXT NOT NULL DEFAULT 'learning',
    scope           TEXT NOT NULL DEFAULT 'shared',
    source_file     TEXT,
    source_type     TEXT NOT NULL DEFAULT 'manual',
    source_project  TEXT,
    oracle_name     TEXT,
    brain_path      TEXT,
    brain_tier      TEXT,
    concepts        JSONB DEFAULT '[]',
    tags            JSONB DEFAULT '[]',
    superseded_by   UUID REFERENCES knowledge_documents(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ,
    search_vector   tsvector,
    UNIQUE(content_hash, scope)
);

-- Trigger to auto-update search_vector from title, content, concepts
CREATE OR REPLACE FUNCTION update_search_vector() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.content, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(
            (SELECT string_agg(value::text, ' ') FROM jsonb_array_elements_text(NEW.concepts) AS value), ''
        )), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

DROP TRIGGER IF EXISTS trg_search_vector ON knowledge_documents;
CREATE TRIGGER trg_search_vector
    BEFORE INSERT OR UPDATE ON knowledge_documents
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

CREATE INDEX IF NOT EXISTS idx_doc_search ON knowledge_documents USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_doc_scope ON knowledge_documents(scope) WHERE superseded_by IS NULL;
CREATE INDEX IF NOT EXISTS idx_doc_type ON knowledge_documents(doc_type) WHERE superseded_by IS NULL;
CREATE INDEX IF NOT EXISTS idx_doc_oracle ON knowledge_documents(oracle_name) WHERE superseded_by IS NULL;
CREATE INDEX IF NOT EXISTS idx_doc_hash ON knowledge_documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_doc_brain_tier ON knowledge_documents(brain_tier) WHERE superseded_by IS NULL;
CREATE INDEX IF NOT EXISTS idx_doc_source_project ON knowledge_documents(source_project) WHERE superseded_by IS NULL;

CREATE TABLE IF NOT EXISTS supersede_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    old_id      UUID NOT NULL REFERENCES knowledge_documents(id),
    new_id      UUID NOT NULL REFERENCES knowledge_documents(id),
    reason      TEXT DEFAULT 'updated',
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scope_registry (
    name        TEXT PRIMARY KEY,
    description TEXT,
    doc_count   INTEGER DEFAULT 0,
    oracle_name TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS concepts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_concepts (
    doc_id      UUID REFERENCES knowledge_documents(id),
    concept_id  UUID REFERENCES concepts(id),
    PRIMARY KEY (doc_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_dc_doc ON document_concepts(doc_id);
CREATE INDEX IF NOT EXISTS idx_dc_concept ON document_concepts(concept_id);

CREATE TABLE IF NOT EXISTS trace (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id   UUID REFERENCES knowledge_documents(id),
    target_id   UUID REFERENCES knowledge_documents(id),
    relation    TEXT NOT NULL,
    confidence  REAL DEFAULT 1.0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trace_source ON trace(source_id);
CREATE INDEX IF NOT EXISTS idx_trace_target ON trace(target_id);