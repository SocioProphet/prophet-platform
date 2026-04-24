# Michael Machine Science

## Purpose

This note records the platform-facing machine-science role for Michael.

Michael is a governed machine-science agent that integrates three epistemic engines under one promotion spine:
- symbolic or neuro-symbolic deduction
- probabilistic-relational belief update
- symbolic-regression candidate-law discovery

## Runtime role in prophet-platform

`prophet-platform` is the governance and eval surface for Michael artifacts.

This repo should own the machine-readable contracts and promotion/evaluation objects for:
- belief states
- equation candidates
- counterexamples
- promotion decisions
- human digital twin state
- evidence packets

## Truth-status separation

Michael should keep these statuses distinct:
- asserted truth
- believed truth
- candidate law
- promoted heuristic
- rejected hypothesis

The platform should not collapse these into one undifferentiated output class.

## Promotion rule

A discovered equation should first become a soft rule or governed heuristic before it is ever treated as an asserted ontology law.

The intended progression is:
- candidate law
- promoted heuristic
- soft rule
- constraint
- asserted truth

## Repo bindings

- semantics: `ontogenesis`
- instance plane: `gaia-world-model`
- governance and eval: `prophet-platform`
- execution packs: `prophet-platform-fabric-mlops-ts-suite`
- public profile and conformance: `socioprophet-agent-standards`
