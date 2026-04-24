-- Run once on existing DBs: psql $DATABASE_URL -f app/db/migrations/002_event_focus.sql
-- (New installs: tables are also appended to app/db/schema.sql)

CREATE TABLE IF NOT EXISTS event_count_snapshots (
    id SERIAL PRIMARY KEY,
    event_count INTEGER NOT NULL,
    markets_in_gamma INTEGER NOT NULL DEFAULT 0,
    source TEXT DEFAULT 'gamma',
    captured_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_embeddings (
    event_id TEXT PRIMARY KEY REFERENCES events (id) ON DELETE CASCADE,
    embedding VECTOR(1024)
);

CREATE TABLE IF NOT EXISTS event_relationships (
    id SERIAL PRIMARY KEY,
    source_event_id TEXT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    target_event_id TEXT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    confidence_score DOUBLE PRECISION NOT NULL,
    evidence JSONB,
    explanation TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT event_rel_pair CHECK (source_event_id <> target_event_id),
    CONSTRAINT event_rel_unique UNIQUE (source_event_id, target_event_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_event_rel_src ON event_relationships (source_event_id);
CREATE INDEX IF NOT EXISTS idx_event_rel_tgt ON event_relationships (target_event_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_captured ON event_count_snapshots (captured_at DESC);
