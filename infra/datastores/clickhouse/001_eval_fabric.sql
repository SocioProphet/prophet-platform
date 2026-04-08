create table if not exists metric_facts (
  ts DateTime,
  metric_fact_id String,
  metric_definition_id String,
  source_descriptor_id String,
  provider_id String,
  model_release_id String,
  benchmark_suite_id String,
  scenario_id String,
  case_id String,
  run_id String,
  trial_id String,
  context_slice_id String,
  risk_tier String,
  autonomy_tier String,
  eval_regime String,
  value_scalar Float64,
  value_json String,
  sample_n UInt32,
  trial_count UInt32,
  cost_usd Float64,
  latency_ms_p50 Float64,
  latency_ms_p95 Float64,
  latency_ms_p99 Float64,
  freshness_days UInt32,
  contamination_risk String,
  reproduced_by_us UInt8,
  source_trust_class String
)
engine = MergeTree
order by (metric_definition_id, model_release_id, ts);

create table if not exists profile_scores (
  ts DateTime,
  profile_score_id String,
  profile_id String,
  subject_kind String,
  subject_id String,
  window String,
  score Float64,
  rank UInt32,
  score_policy_id String
)
engine = MergeTree
order by (profile_id, subject_id, ts);
