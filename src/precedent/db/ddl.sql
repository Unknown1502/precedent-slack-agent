-- Precedent canon schema. SOURCE OF TRUTH for migrations.
-- `__EMBED_DIM__` is substituted by migrate.py from settings.embed_dim before execution.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS decisions (
    id            text PRIMARY KEY,                      -- e.g. 'PRE-014'
    title         text NOT NULL,
    statement     text NOT NULL,
    rationale     text,
    alternatives  jsonb,
    dissent       jsonb,
    scope         text,
    status        text NOT NULL DEFAULT 'proposed',      -- proposed|ratified|superseded|expired
    decided_by    text[],
    ratified_by   text,
    supersedes_id text REFERENCES decisions(id),
    superseded_by text,
    expires_hint  text,
    evidence      jsonb NOT NULL DEFAULT '[]'::jsonb,     -- [{permalink, channel_id, ts, quote}]
    embedding     vector(__EMBED_DIM__),
    decided_at    date,                                   -- narrative date (Gotcha G3)
    created_at    timestamptz DEFAULT now(),
    team_id       text NOT NULL
);

CREATE TABLE IF NOT EXISTS drift_events (
    id                bigserial PRIMARY KEY,
    decision_id       text REFERENCES decisions(id),
    message_permalink text,
    channel_id        text,
    author            text,
    claim             text,
    confidence        real,
    resolution        text DEFAULT 'open',                -- open|aligned|superseded|dismissed
    created_at        timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS channel_enrollment (
    channel_id text PRIMARY KEY,
    mode       text DEFAULT 'observe'                     -- observe|manual_only
);

CREATE TABLE IF NOT EXISTS meta (
    key   text PRIMARY KEY,
    value text
);

-- Cosine similarity index for local drift search (hot path never calls RTS).
CREATE INDEX IF NOT EXISTS idx_decisions_embedding
    ON decisions USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions (status);
CREATE INDEX IF NOT EXISTS idx_drift_events_resolution ON drift_events (resolution);
