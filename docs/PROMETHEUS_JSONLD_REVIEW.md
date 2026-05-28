# PROMETHEUS JSON-LD Review Artifact

Status: v0.1 semantic review handoff.

This tranche emits an Ontogenesis-compatible JSON-LD review artifact from a PROMETHEUS candidate and an SRRunArtifact.

## Boundary

The JSON-LD artifact is a semantic review proposal only.

It does not mutate Ontogenesis.

It does not require WebProtege.

It does not create a law.

It does not create policy or runtime authority.

## Inputs

- Platform candidate artifact.
- AgentPlane-compatible SRRunArtifact.

## Output

The output JSON-LD uses `@type: sr:SRAssertionProposal` and includes:

- `sr:vocabVersion`
- `sr:vocabularyPromotionState`
- dataset evidence
- fit metric
- complexity metric
- dimensional analysis
- evidence replay reference
- discovery method reference
- promotion status
- review state
- semantic review surface
- non-authority declaration
- equation text

## Review surfaces

The default review surface is `automated_shacl_gate`, but the CLI accepts another configured review surface. WebProtege remains optional.

## Validation

Run:

`python3 tools/validate_prometheus_jsonld_review.py build/prometheus/jsonld-review/sr-review.jsonld`
