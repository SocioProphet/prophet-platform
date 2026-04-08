insert into metric_definitions (
  metric_definition_id, name, family, regime, unit,
  direction, value_type, normalizer
) values
  (
    'md_denotation_accuracy',
    'denotation_accuracy',
    'semantic_compiler',
    'CWA_BINARY',
    'ratio',
    'higher_better',
    'scalar',
    'bounded_0_1'
  ),
  (
    'md_false_allow_rate',
    'false_allow_rate',
    'safety_governance',
    'POLICY',
    'ratio',
    'lower_better',
    'scalar',
    'bounded_0_1'
  ),
  (
    'md_latency_ms_p95',
    'latency_ms_p95',
    'operations_economics',
    'OPERATIONS',
    'ms',
    'lower_better',
    'scalar',
    'latency_inverse'
  )
on conflict do nothing;
