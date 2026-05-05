-- Personal Intelligence Cell control-plane schema
-- Status: draft migration for apps/cell-service persistence lane
--
-- The first Postgres repository seam is body-first: each object is stored as
-- canonical JSONB while selected generated columns expose indexable fields.
-- This keeps the generic repository small without losing query ergonomics.

CREATE TABLE IF NOT EXISTS cell_cells (
  id TEXT PRIMARY KEY,
  body JSONB NOT NULL,
  owner_ref TEXT GENERATED ALWAYS AS (body->>'owner_ref') STORED,
  kind TEXT GENERATED ALWAYS AS (body->>'kind') STORED,
  display_name TEXT GENERATED ALWAYS AS (body->>'display_name') STORED,
  policy_ref TEXT GENERATED ALWAYS AS (body->>'policy_ref') STORED,
  memory_ref TEXT GENERATED ALWAYS AS (body->>'memory_ref') STORED,
  config_ref TEXT GENERATED ALWAYS AS (body->>'config_ref') STORED,
  state TEXT GENERATED ALWAYS AS (COALESCE(body->>'state', 'active')) STORED,
  created_at TIMESTAMPTZ GENERATED ALWAYS AS ((body->>'created_at')::timestamptz) STORED,
  updated_at TIMESTAMPTZ GENERATED ALWAYS AS ((body->>'updated_at')::timestamptz) STORED,
  CHECK (kind IN ('personal', 'project', 'community', 'organization', 'mission')),
  CHECK (state IN ('draft', 'active', 'paused', 'archived', 'revoked'))
);

CREATE TABLE IF NOT EXISTS cell_configs (
  cell_id TEXT PRIMARY KEY REFERENCES cell_cells(id) ON DELETE CASCADE,
  body JSONB NOT NULL,
  data_location_policy TEXT GENERATED ALWAYS AS (body->>'data_location_policy') STORED,
  sync_policy TEXT GENERATED ALWAYS AS (body->>'sync_policy') STORED,
  backup_policy TEXT GENERATED ALWAYS AS (body->>'backup_policy') STORED,
  local_first_mode BOOLEAN GENERATED ALWAYS AS ((body->>'local_first_mode')::boolean) STORED,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cell_sources (
  id TEXT PRIMARY KEY,
  body JSONB NOT NULL,
  kind TEXT GENERATED ALWAYS AS (body->>'kind') STORED,
  uri TEXT GENERATED ALWAYS AS (body->>'uri') STORED,
  policy_ref TEXT GENERATED ALWAYS AS (body->>'policy_ref') STORED,
  enabled BOOLEAN GENERATED ALWAYS AS (COALESCE((body->>'enabled')::boolean, TRUE)) STORED,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cell_watches (
  id TEXT PRIMARY KEY,
  body JSONB NOT NULL,
  cell_id TEXT GENERATED ALWAYS AS (body->>'cell_id') STORED REFERENCES cell_cells(id) ON DELETE CASCADE,
  state TEXT GENERATED ALWAYS AS (body->>'state') STORED,
  relevance_policy TEXT GENERATED ALWAYS AS (body->>'relevance_policy') STORED,
  notification_policy TEXT GENERATED ALWAYS AS (body->>'notification_policy') STORED,
  created_at TIMESTAMPTZ GENERATED ALWAYS AS ((body->>'created_at')::timestamptz) STORED,
  updated_at TIMESTAMPTZ GENERATED ALWAYS AS ((body->>'updated_at')::timestamptz) STORED,
  CHECK (state IN ('draft', 'active', 'paused', 'archived'))
);

CREATE TABLE IF NOT EXISTS cell_watch_patterns (
  id TEXT PRIMARY KEY,
  body JSONB NOT NULL,
  watch_id TEXT GENERATED ALWAYS AS (body->>'watch_id') STORED REFERENCES cell_watches(id) ON DELETE CASCADE,
  pattern_kind TEXT GENERATED ALWAYS AS (body->>'pattern_kind') STORED,
  raw_expression TEXT GENERATED ALWAYS AS (body->>'raw_expression') STORED,
  version TEXT GENERATED ALWAYS AS (body->>'version') STORED,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cell_signals (
  id TEXT PRIMARY KEY,
  body JSONB NOT NULL,
  cell_id TEXT GENERATED ALWAYS AS (body->>'cell_id') STORED REFERENCES cell_cells(id) ON DELETE CASCADE,
  source_id TEXT GENERATED ALWAYS AS (body->>'source_id') STORED REFERENCES cell_sources(id),
  watch_id TEXT GENERATED ALWAYS AS (body->>'watch_id') STORED REFERENCES cell_watches(id) ON DELETE CASCADE,
  observed_at TIMESTAMPTZ GENERATED ALWAYS AS ((body->>'observed_at')::timestamptz) STORED,
  novelty_score DOUBLE PRECISION GENERATED ALWAYS AS ((body->>'novelty_score')::double precision) STORED,
  relevance_score DOUBLE PRECISION GENERATED ALWAYS AS ((body->>'relevance_score')::double precision) STORED,
  confidence_score DOUBLE PRECISION GENERATED ALWAYS AS ((body->>'confidence_score')::double precision) STORED,
  source_trust_score DOUBLE PRECISION GENERATED ALWAYS AS ((body->>'source_trust_score')::double precision) STORED,
  policy_status TEXT GENERATED ALWAYS AS (body->>'policy_status') STORED,
  evidence_refs JSONB GENERATED ALWAYS AS (body->'evidence_refs') STORED,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (novelty_score >= 0 AND novelty_score <= 1),
  CHECK (relevance_score >= 0 AND relevance_score <= 1),
  CHECK (confidence_score >= 0 AND confidence_score <= 1),
  CHECK (source_trust_score IS NULL OR (source_trust_score >= 0 AND source_trust_score <= 1))
);

CREATE TABLE IF NOT EXISTS cell_feed_items (
  id TEXT PRIMARY KEY,
  body JSONB NOT NULL,
  cell_id TEXT GENERATED ALWAYS AS (body->>'cell_id') STORED REFERENCES cell_cells(id) ON DELETE CASCADE,
  signal_id TEXT GENERATED ALWAYS AS (body->>'signal_id') STORED REFERENCES cell_signals(id) ON DELETE CASCADE,
  feed_kind TEXT GENERATED ALWAYS AS (body->>'feed_kind') STORED,
  policy_decision JSONB GENERATED ALWAYS AS (body->'policy_decision') STORED,
  created_at TIMESTAMPTZ GENERATED ALWAYS AS ((body->>'created_at')::timestamptz) STORED
);

CREATE TABLE IF NOT EXISTS cell_intent_events (
  id TEXT PRIMARY KEY,
  body JSONB NOT NULL,
  cell_id TEXT GENERATED ALWAYS AS (body->>'cell_id') STORED REFERENCES cell_cells(id) ON DELETE CASCADE,
  actor_ref TEXT GENERATED ALWAYS AS (body->>'actor_ref') STORED,
  intent_text TEXT GENERATED ALWAYS AS (body->>'intent_text') STORED,
  structured_intent JSONB GENERATED ALWAYS AS (body->'structured_intent') STORED,
  policy_decision JSONB GENERATED ALWAYS AS (body->'policy_decision') STORED,
  emitted_events JSONB GENERATED ALWAYS AS (COALESCE(body->'emitted_events', '[]'::jsonb)) STORED,
  created_at TIMESTAMPTZ GENERATED ALWAYS AS ((body->>'created_at')::timestamptz) STORED
);

CREATE TABLE IF NOT EXISTS cell_feedback_events (
  id TEXT PRIMARY KEY,
  body JSONB NOT NULL,
  cell_id TEXT GENERATED ALWAYS AS (body->>'cell_id') STORED REFERENCES cell_cells(id) ON DELETE CASCADE,
  signal_id TEXT GENERATED ALWAYS AS (body->>'signal_id') STORED REFERENCES cell_signals(id) ON DELETE CASCADE,
  actor_ref TEXT GENERATED ALWAYS AS (body->>'actor_ref') STORED,
  action TEXT GENERATED ALWAYS AS (body->>'action') STORED,
  created_at TIMESTAMPTZ GENERATED ALWAYS AS ((body->>'created_at')::timestamptz) STORED
);

CREATE TABLE IF NOT EXISTS cell_archives (
  id TEXT PRIMARY KEY,
  body JSONB NOT NULL,
  cell_id TEXT GENERATED ALWAYS AS (body->>'cell_id') STORED REFERENCES cell_cells(id) ON DELETE CASCADE,
  schema_version TEXT GENERATED ALWAYS AS (body->>'schema_version') STORED,
  manifest JSONB GENERATED ALWAYS AS (body->'manifest') STORED,
  restore_dry_run_report_ref TEXT GENERATED ALWAYS AS (body->>'restore_dry_run_report_ref') STORED,
  created_at TIMESTAMPTZ GENERATED ALWAYS AS ((body->>'created_at')::timestamptz) STORED
);

CREATE INDEX IF NOT EXISTS idx_cell_watches_cell_id ON cell_watches(cell_id);
CREATE INDEX IF NOT EXISTS idx_cell_patterns_watch_id ON cell_watch_patterns(watch_id);
CREATE INDEX IF NOT EXISTS idx_cell_signals_cell_watch ON cell_signals(cell_id, watch_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_cell_feed_items_cell_created ON cell_feed_items(cell_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cell_intent_events_cell_created ON cell_intent_events(cell_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cell_feedback_events_signal ON cell_feedback_events(signal_id);
