# PROMETHEUS PySR MVP

Status: v0.1 platform executable smoke.

This tranche creates the first Prophet Platform executable surface for PROMETHEUS equation-candidate emission.

It is intentionally not a full PySR runtime integration. The script emits a governed `EquationCandidate` artifact using a deterministic linear fallback so CI can validate the artifact contract, dataset hashing, units gate posture, and non-authority boundary without installing PySR or Julia.

## Boundary

The emitted artifact is not a law, ontology assertion, policy, controller, or admitted SRAssertion.

AgentPlane owns replay/evidence contracts. Ontogenesis owns the SR vocabulary. SocioSphere owns rollout doctrine. This platform tranche only proves that runtime code can emit the candidate shape.

## Units gate

The MVP records `unitsStatus` as `consistent`, `inconsistent`, `unknown`, or `unchecked`.

A candidate with inconsistent units is rejected at candidate level and must not be promoted.

## Validation

Run:

`python3 tools/prometheus_pysr_mvp.py --data tests/fixtures/prometheus/pysr-mvp-linear.csv --target y --dataset-uri urn:dataset:prometheus:pysr-mvp-linear --target-unit meter --feature-unit x=meter --generated-at 2026-05-27T18:30:00Z --output build/prometheus/pysr-mvp/equation-candidate.json`

Then validate:

`python3 tools/validate_prometheus_pysr_mvp_artifact.py build/prometheus/pysr-mvp/equation-candidate.json --expect-units consistent`

## Next tranche

After this smoke lands, the real PySR integration can replace the fallback fitter behind the same candidate artifact contract.
