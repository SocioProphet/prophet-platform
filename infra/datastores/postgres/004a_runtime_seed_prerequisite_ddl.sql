-- Missing DDL for tables that 005_eval_fabric_runtime_seed.sql inserts into and the
-- eval-fabric-api reads, but whose CREATE TABLE existed NOWHERE in version control — so a fresh
-- eval_fabric_migrate failed at 005 (the same class of gap as metric_crosswalks, fixed in 004).
-- Surfaced by tools/lint_eval_fabric_migrations.py. Ordered before 005 (sorts 004 < 004a < 005).
-- Columns are 005's exact insert lists; types from the canonical schemas/eval/*.schema.json
-- (required -> NOT NULL). No FKs: matches the text-id, LEFT-JOIN convention of source_descriptors
-- / metric_definitions / metric_crosswalks.

create table if not exists methodology_snapshots (
  methodology_snapshot_id text primary key,
  source_descriptor_id text not null,
  hash text not null,
  captured_at timestamptz not null,
  url text,
  notes text
);

create table if not exists repro_ledger_entries (
  repro_ledger_entry_id text primary key,
  run_id text not null,
  prompt_pack_id text,
  fixture_snapshot_id text,
  tool_bundle_id text,
  seed_policy text,
  environment_hash text not null,
  methodology_snapshot_hash text not null,
  replay_artifact_id text,
  notes text
);

create table if not exists causal_attributions (
  causal_attribution_id text primary key,
  subject_id text not null,
  window text not null,
  attributions jsonb not null,
  notes text
);
