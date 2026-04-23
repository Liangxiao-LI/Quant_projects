-- PostgreSQL + pgvector schema for Polymarket multi-agent storage.
-- Embedding dimension must match BEDROCK_EMBEDDING_DIMENSION (default 1024 for Titan v2).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    slug TEXT,
    title TEXT,
    description TEXT,
    series_id TEXT,
    active BOOLEAN,
    closed BOOLEAN,
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    payload JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS markets (
    id TEXT PRIMARY KEY,
    event_id TEXT REFERENCES events (id),
    slug TEXT,
    question TEXT,
    description TEXT,
    condition_id TEXT,
    series_id TEXT,
    active BOOLEAN,
    closed BOOLEAN,
    volume DOUBLE PRECISION,
    liquidity DOUBLE PRECISION,
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    tags TEXT[],
    outcome_names TEXT[],
    clob_token_ids TEXT[],
    payload JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_embeddings (
    market_id TEXT PRIMARY KEY REFERENCES markets (id) ON DELETE CASCADE,
    embedding VECTOR(1024)
);

CREATE TABLE IF NOT EXISTS market_entities (
    id SERIAL PRIMARY KEY,
    market_id TEXT REFERENCES markets (id) ON DELETE CASCADE,
    entity JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS relationships (
    id SERIAL PRIMARY KEY,
    source_market_id TEXT NOT NULL REFERENCES markets (id) ON DELETE CASCADE,
    target_market_id TEXT NOT NULL REFERENCES markets (id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    confidence_score DOUBLE PRECISION NOT NULL,
    evidence JSONB,
    explanation TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT relationships_pair_order CHECK (source_market_id <> target_market_id),
    CONSTRAINT relationships_unique_pair UNIQUE (source_market_id, target_market_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_markets_event ON markets (event_id);
CREATE INDEX IF NOT EXISTS idx_markets_series ON markets (series_id);
CREATE INDEX IF NOT EXISTS idx_markets_tags ON markets USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships (source_market_id);
CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships (target_market_id);

-- Optional Neo4j remains out of SQL; see GraphStorageAgent for future dual-write.
