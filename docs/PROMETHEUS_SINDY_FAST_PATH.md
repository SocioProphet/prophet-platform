# PROMETHEUS SINDy Fast Path

Status: v0.1 platform dynamics candidate emitter.

This tranche adds the first Prophet Platform SINDy-style fast path for time-series dynamics. It emits a `PlatformDynamicsCandidate` artifact from a simple time-series CSV and records a candidate first-order dynamics equation.

## Boundary

This is not an autoscaling policy, routing policy, remediation policy, controller, or runtime authority.

`controlAuthority` is always false. Downstream systems must treat the output as governed evidence only.

## Scope

The implementation is intentionally minimal and deterministic. It uses finite differences and a linear dynamics fit as the platform smoke for the SINDy lane. It does not install PySINDy as a required dependency and it does not execute production control.

## Output

The emitted artifact includes:

- `artifactType: PlatformDynamicsCandidate`
- `applicationMode: platform_dynamics`
- `methodFamily: sindy`
- `implementationMode: sindy_linear_fast_path`
- dataset URI and SHA-256 content hash
- fitted dynamics equation
- NMSE fit metric
- complexity
- `controlAuthority: false`
- explicit non-authority declaration

## Validation

Run:

`python3 tools/prometheus_sindy_fast_path.py --data tests/fixtures/prometheus/sindy-fast-path-linear.csv --time-column t --value-column q --dataset-uri urn:dataset:prometheus:sindy-fast-path-linear --generated-at 2026-05-27T19:30:00Z --output build/prometheus/sindy-fast-path/platform-dynamics-candidate.json`

Then validate:

`python3 tools/validate_prometheus_sindy_candidate.py build/prometheus/sindy-fast-path/platform-dynamics-candidate.json`

## Next tranche

A later tranche may add optional real PySINDy execution behind this same artifact posture. PySINDy must remain optional until dependency and replay posture are pinned.
