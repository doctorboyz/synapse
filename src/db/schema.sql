-- synapse PostgreSQL schema (idempotent — safe to run on every startup)

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

-- Summary column for auto-summarization
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS summary TEXT;

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

-- Project registry for cross-project search
CREATE TABLE IF NOT EXISTS registered_projects (
    scope           TEXT PRIMARY KEY,
    project_path    TEXT NOT NULL,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Search topics per scope — web/social monitoring
CREATE TABLE IF NOT EXISTS search_topics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope           TEXT NOT NULL,
    topic           TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'web',  -- web, twitter, reddit, hn, youtube
    frequency       TEXT NOT NULL DEFAULT 'daily', -- hourly, daily, weekly
    last_searched   TIMESTAMPTZ,
    enabled         BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(scope, topic, source)
);
CREATE INDEX IF NOT EXISTS idx_search_topic_scope ON search_topics(scope);
CREATE INDEX IF NOT EXISTS idx_search_topic_enabled ON search_topics(enabled) WHERE enabled = true;

-- Reconcile log — persistent audit trail
CREATE TABLE IF NOT EXISTS reconcile_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    scope           TEXT,
    dry_run         BOOLEAN DEFAULT false,
    merged_duplicates   INTEGER DEFAULT 0,
    removed_duplicates  INTEGER DEFAULT 0,
    conflicts_found     INTEGER DEFAULT 0,
    conflicts_resolved  INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'running',  -- running, completed, failed
    error_message   TEXT
);
CREATE INDEX IF NOT EXISTS idx_reconcile_log_started ON reconcile_log(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_reconcile_log_status ON reconcile_log(status);

-- Pending reviews — LINE confirmation flow
CREATE TABLE IF NOT EXISTS pending_reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    summary         TEXT,
    scope           TEXT NOT NULL DEFAULT 'shared',
    doc_type        TEXT NOT NULL DEFAULT 'note',
    source_type     TEXT NOT NULL DEFAULT 'line',
    source_project  TEXT,
    oracle_name     TEXT,
    tags            JSONB DEFAULT '[]',
    concepts        JSONB DEFAULT '[]',
    metadata        JSONB DEFAULT '{}',
    reply_token     TEXT,
    user_id         TEXT,
    chat_id         TEXT,
    status          TEXT DEFAULT 'pending',  -- pending, confirmed, cancelled, expired
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '1 hour'
);
CREATE INDEX IF NOT EXISTS idx_pending_user ON pending_reviews(user_id, status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_pending_chat ON pending_reviews(chat_id, status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_pending_expires ON pending_reviews(expires_at);