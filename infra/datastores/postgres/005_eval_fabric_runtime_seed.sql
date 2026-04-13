insert into eval_runs (
  run_id, run_type, status, started_at, completed_at,
  provider_id, model_release_id, source_descriptor_id,
  seed_policy, reproducibility_mode
) values (
  'run_001',
  'offline_eval',
  'completed',
  now() - interval '10 minutes',
  now(),
  'our_platform',
  'model.semantic-stack.2026-04-05',
  'src_internal_eval_runner',
  'three_trial_fixed_seed_set',
  'strict'
)
on conflict do nothing;

insert into trials (
  trial_id, run_id, case_id, attempt_index, seed,
  candidate_count, clarification_count, tool_call_count,
  retry_count, rollback_count, status, outcome_label,
  replay_artifact_id
) values (
  'trial_001',
  'run_001',
  'case_best_mailings_2017',
  1,
  42,
  4,
  0,
  2,
  1,
  0,
  'completed',
  'success',
  'replay_001'
)
on conflict do nothing;

insert into methodology_snapshots (
  methodology_snapshot_id, source_descriptor_id, hash,
  captured_at, url, notes
) values (
  'ms_001',
  'src_internal_eval_runner',
  'sha256:runner-v1',
  now(),
  'internal://eval-runner/v1',
  'Internal methodology snapshot for seeded runtime path.'
)
on conflict do nothing;

insert into repro_ledger_entries (
  repro_ledger_entry_id, run_id, prompt_pack_id,
  fixture_snapshot_id, tool_bundle_id, seed_policy,
  environment_hash, methodology_snapshot_hash,
  replay_artifact_id, notes
) values (
  'repro_001',
  'run_001',
  'promptpack.eval.v2',
  'fixture_ranked_001@sha256:abc123',
  'tools.bundle.prod.v5',
  'three_trial_fixed_seed_set',
  'sha256:env-001',
  'sha256:runner-v1',
  'replay_001',
  'Seed reproducibility ledger entry for platform runtime adoption.'
)
on conflict do nothing;

insert into causal_attributions (
  causal_attribution_id, subject_id, window, attributions, notes
) values (
  'causal_001',
  'model.semantic-stack.2026-04-05',
  'rolling_30d',
  '{"model_delta":0.03,"scaffold_delta":0.01,"ontology_delta":0.02,"retrieval_delta":0.0,"benchmark_drift":-0.01,"judge_drift":0.0}'::jsonb,
  'Seed attribution decomposition for profile-score drift explanation.'
)
on conflict do nothing;

insert into metric_crosswalks (
  metric_crosswalk_id, source_descriptor_id, source_metric_name,
  canonical_metric_definition_id, transform_notes
) values (
  'crosswalk_001',
  'src_internal_eval_runner',
  'denotation_accuracy',
  'md_denotation_accuracy',
  'Seed crosswalk record for runtime provenance responses.'
)
on conflict do nothing;
