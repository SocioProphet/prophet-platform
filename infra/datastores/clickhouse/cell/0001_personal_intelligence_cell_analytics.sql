-- Personal Intelligence Cell analytical fact schema
-- Status: draft analytical-plane stub for apps/cell-service evaluation and observability lane

CREATE TABLE IF NOT EXISTS cell_signal_scores
(
  cell_id String,
  signal_id String,
  source_id String,
  watch_id String,
  observed_at DateTime64(3, 'UTC'),
  novelty_score Float64,
  relevance_score Float64,
  confidence_score Float64,
  source_trust_score Float64,
  policy_status LowCardinality(String),
  created_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(observed_at)
ORDER BY (cell_id, watch_id, observed_at, signal_id);

CREATE TABLE IF NOT EXISTS cell_source_quality_facts
(
  cell_id String,
  source_id String,
  source_kind LowCardinality(String),
  event_at DateTime64(3, 'UTC'),
  relevance_mean Float64,
  confidence_mean Float64,
  accepted_count UInt64,
  rejected_count UInt64,
  muted_count UInt64,
  promoted_count UInt64
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(event_at)
ORDER BY (cell_id, source_id, event_at);

CREATE TABLE IF NOT EXISTS cell_reputation_deltas
(
  cell_id String,
  subject_ref String,
  subject_kind LowCardinality(String),
  context String,
  delta Float64,
  confidence_low Float64,
  confidence_high Float64,
  anti_manipulation_flags Array(String),
  event_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_at)
ORDER BY (cell_id, subject_kind, subject_ref, event_at);

CREATE TABLE IF NOT EXISTS cell_feedback_outcomes
(
  cell_id String,
  signal_id String,
  source_id String,
  watch_id String,
  actor_ref String,
  action LowCardinality(String),
  event_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_at)
ORDER BY (cell_id, watch_id, action, event_at);

CREATE TABLE IF NOT EXISTS cell_watch_pattern_metrics
(
  cell_id String,
  watch_id String,
  pattern_id String,
  pattern_kind LowCardinality(String),
  event_at DateTime64(3, 'UTC'),
  match_count UInt64,
  accepted_count UInt64,
  rejected_count UInt64,
  extraction_error_count UInt64
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(event_at)
ORDER BY (cell_id, watch_id, pattern_id, event_at);

CREATE TABLE IF NOT EXISTS cell_notification_metrics
(
  cell_id String,
  feed_kind LowCardinality(String),
  event_at DateTime64(3, 'UTC'),
  emitted_count UInt64,
  dismissed_count UInt64,
  saved_count UInt64,
  shared_count UInt64
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(event_at)
ORDER BY (cell_id, feed_kind, event_at);

CREATE TABLE IF NOT EXISTS cell_social_environment_snapshots
(
  cell_id String,
  snapshot_at DateTime64(3, 'UTC'),
  peer_count UInt64,
  stale_tie_count UInt64,
  emerging_community_count UInt64,
  attention_sink_count UInt64,
  coordinated_amplification_flags Array(String),
  body String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(snapshot_at)
ORDER BY (cell_id, snapshot_at);
