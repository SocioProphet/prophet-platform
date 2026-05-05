-- Personal Intelligence Cell control-plane schema
-- Status: draft migration stub for apps/cell-service persistence lane

CREATE TABLE IF NOT EXISTS cell_cells (
  id TEXT PRIMARY KEY,
  owner_ref TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('personal', 'project', 'community', 'organization', 'mission')),
  display_name TEXT,
  policy_ref TEXT NOT NULL,
  memory_ref TEXT NOT NULL,
  config_ref TEXT,
  state TEXT NOT NULL DEFAULT 'active' CHECK (state IN ('draft', 'active', 'paused', 'archived', 'revoked')),
  body JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS cell_configs (
  cell_id TEXT PRIMARY KEY REFERENCES cell_cells(id) ON DELETE CASCADE,
  data_location_policy TEXT NOT NULL,
  sync_policy TEXT NOT NULL,
  backup_policy TEXT NOT NULL,
  local_first_mode BOOLEAN NOT NULL,
  body JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cell_sources (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  uri TEXT NOT NULL,
  policy_ref TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  body JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cell_watches (
  id TEXT PRIMARY KEY,
  cell_id TEXT NOT NULL REFERENCES cell_cells(id) ON DELETE CASCADE,
  state TEXT NOT NULL CHECK (state IN ('draft', 'active', 'paused', 'archived')),
  relevance_policy TEXT NOT NULL,
  notification_policy TEXT NOT NULL,
  body JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS cell_watch_patterns (
  id TEXT PRIMARY KEY,
  watch_id TEXT NOT NULL REFERENCES cell_watches(id) ON DELETE CASCADE,
  pattern_kind TEXT NOT NULL,
  raw_expression TEXT NOT NULL,
  version TEXT NOT NULL,
  body JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cell_signals (
  id TEXT PRIMARY KEY,
  cell_id TEXT NOT NULL REFERENCES cell_cells(id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES cell_sources(id),
  watch_id TEXT NOT NULL REFERENCES cell_watches(id) ON DELETE CASCADE,
  observed_at TIMESTAMPTZ NOT NULL,
  novelty_score DOUBLE PRECISION NOT NULL CHECK (novelty_score >= 0 AND novelty_score <= 1),
  relevance_score DOUBLE PRECISION NOT NULL CHECK (relevance_score >= 0 AND relevance_score <= 1),
  confidence_score DOUBLE PRECISION NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  source_trust_score DOUBLE PRECISION CHECK (source_trust_score >= 0 AND source_trust_score <= 1),
  policy_status TEXT NOT NULL,
  evidence_refs JSONB NOT NULL,
  body JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cell_feed_items (
  id TEXT PRIMARY KEY,
  cell_id TEXT NOT NULL REFERENCES cell_cells(id) ON DELETE CASCADE,
  signal_id TEXT NOT NULL REFERENCES cell_signals(id) ON DELETE CASCADE,
  feed_kind TEXT NOT NULL,
  policy_decision JSONB NOT NULL,
  body JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS cell_intent_events (
  id TEXT PRIMARY KEY,
  cell_id TEXT NOT NULL REFERENCES cell_cells(id) ON DELETE CASCADE,
  actor_ref TEXT NOT NULL,
  intent_text TEXT NOT NULL,
  structured_intent JSONB NOT NULL,
  policy_decision JSONB NOT NULL,
  emitted_events JSONB NOT NULL DEFAULT '[]'::jsonb,
  body JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS cell_feedback_events (
  id TEXT PRIMARY KEY,
  cell_id TEXT NOT NULL REFERENCES cell_cells(id) ON DELETE CASCADE,
  signal_id TEXT NOT NULL REFERENCES cell_signals(id) ON DELETE CASCADE,
  actor_ref TEXT NOT NULL,
  action TEXT NOT NULL,
  body JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS cell_archives (
  id TEXT PRIMARY KEY,
  cell_id TEXT NOT NULL REFERENCES cell_cells(id) ON DELETE CASCADE,
  schema_version TEXT NOT NULL,
  manifest JSONB NOT NULL,
  restore_dry_run_report_ref TEXT,
  body JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cell_watches_cell_id ON cell_watches(cell_id);
CREATE INDEX IF NOT EXISTS idx_cell_patterns_watch_id ON cell_watch_patterns(watch_id);
CREATE INDEX IF NOT EXISTS idx_cell_signals_cell_watch ON cell_signals(cell_id, watch_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_cell_feed_items_cell_created ON cell_feed_items(cell_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cell_intent_events_cell_created ON cell_intent_events(cell_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cell_feedback_events_signal ON cell_feedback_events(signal_id);
