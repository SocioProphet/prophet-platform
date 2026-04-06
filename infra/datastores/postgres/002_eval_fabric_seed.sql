insert into source_descriptors (
  source_descriptor_id, source_type, name, publisher, default_trust_weight,
  reproducibility_expectation, methodology_snapshot_hash
) values
  ('src_internal_eval_runner', 'internal_reproduced', 'Internal Eval Runner', 'our_platform', 1.0, 'high', 'sha256:runner-v1'),
  ('src_provider_openai_system_card', 'official_provider', 'OpenAI GPT-5 System Card', 'OpenAI', 0.70, 'medium', 'sha256:gpt5-system-card'),
  ('src_provider_google_fsf_v3', 'official_provider', 'Google Frontier Safety Framework', 'Google DeepMind', 0.70, 'medium', 'sha256:google-fsf-v3')
on conflict do nothing;

insert into context_slices (
  context_slice_id, length_bucket, modality_mix, ontology_depth_bucket,
  relation_chain_bucket, ambiguity_bucket, tool_count_bucket,
  freshness_requirement, latency_budget, cost_budget,
  risk_tier, autonomy_tier, domain
) values
  (
    'ctx_high_assurance_code_agent',
    '32k_to_128k',
    '["text", "code"]'::jsonb,
    '4_to_6',
    '3_to_4',
    '2',
    '3_to_5',
    'live_or_recent',
    'interactive',
    'medium',
    'high',
    'tool_using_agent',
    'software_engineering'
  )
on conflict do nothing;

insert into competitor_snapshots (
  competitor_snapshot_id, snapshot_ts, provider_id, model_release_id,
  source_descriptor_id, freshness_days, source_trust_class,
  reproduced_by_us, strategic_relevance, payload
) values
  (
    'cmp_openai_gpt5',
    now(),
    'openai',
    'gpt5_aug2025',
    'src_provider_openai_system_card',
    235,
    'official_provider',
    false,
    'high',
    '{"notes": ["Seed competitor snapshot for platform radar."]}'::jsonb
  ),
  (
    'cmp_google_gemini',
    now(),
    'google',
    'gemini_family_current',
    'src_provider_google_fsf_v3',
    195,
    'official_provider',
    false,
    'high',
    '{"notes": ["Seed competitor snapshot for platform radar."]}'::jsonb
  )
on conflict do nothing;
