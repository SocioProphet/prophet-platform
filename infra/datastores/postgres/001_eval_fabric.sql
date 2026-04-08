create table if not exists metric_definitions (
  metric_definition_id text primary key,
  name text not null,
  family text not null,
  regime text not null,
  unit text not null,
  direction text not null,
  value_type text not null,
  normalizer text not null,
  created_at timestamptz not null default now()
);

create table if not exists source_descriptors (
  source_descriptor_id text primary key,
  source_type text not null,
  name text not null,
  publisher text not null,
  default_trust_weight double precision not null,
  reproducibility_expectation text not null,
  methodology_snapshot_hash text not null,
  created_at timestamptz not null default now()
);

create table if not exists context_slices (
  context_slice_id text primary key,
  length_bucket text not null,
  modality_mix jsonb not null,
  ontology_depth_bucket text not null,
  relation_chain_bucket text not null,
  ambiguity_bucket text not null,
  tool_count_bucket text not null,
  freshness_requirement text not null,
  latency_budget text not null,
  cost_budget text not null,
  risk_tier text not null,
  autonomy_tier text not null,
  domain text not null,
  created_at timestamptz not null default now()
);

create table if not exists eval_runs (
  run_id text primary key,
  run_type text not null,
  status text not null,
  started_at timestamptz not null,
  completed_at timestamptz,
  provider_id text not null,
  model_release_id text not null,
  source_descriptor_id text not null,
  seed_policy text not null,
  reproducibility_mode text not null,
  created_at timestamptz not null default now()
);

create table if not exists trials (
  trial_id text primary key,
  run_id text not null references eval_runs(run_id) on delete cascade,
  case_id text not null,
  attempt_index integer not null,
  seed integer,
  candidate_count integer,
  clarification_count integer,
  tool_call_count integer,
  retry_count integer,
  rollback_count integer,
  status text not null,
  outcome_label text not null,
  replay_artifact_id text,
  created_at timestamptz not null default now()
);

create table if not exists competitor_snapshots (
  competitor_snapshot_id text primary key,
  snapshot_ts timestamptz not null,
  provider_id text not null,
  model_release_id text not null,
  source_descriptor_id text not null,
  freshness_days integer not null,
  source_trust_class text not null,
  reproduced_by_us boolean not null,
  strategic_relevance text not null,
  payload jsonb not null,
  created_at timestamptz not null default now()
);
