# Prophet Understand / Repo Intelligence v0

## Status

This document defines the first governed repo-understanding lane for Prophet Platform.

Parent issue: #407

## Purpose

Prophet Understand turns each important repository into a governed, searchable, agent-usable graph artifact. The goal is not a decorative dependency map. The goal is a trusted operating model for humans and agents: what exists, what depends on it, what changed, what evidence supports it, what policy applies, and what action is safe next.

This lane absorbs the useful product pattern from contemporary open-source codebase graph tools while retaining SocioProphet requirements: provenance, validation, policy gates, source anchors, diff impact analysis, agent identity, and cross-repo governance.

## Core artifact

The canonical artifact name for v0 is:

```text
.prophet/prophet-understanding.json
```

A repository may also publish compatibility aliases such as `sociograph.json`, but downstream systems should treat `prophet-understanding.json` as the canonical v0 path.

## Required top-level fields

```json
{
  "schema_version": "prophet-understanding.v0",
  "repo": {
    "full_name": "SocioProphet/example",
    "default_branch": "main",
    "commit": "<git-sha>",
    "generated_at": "<rfc3339>",
    "artifact_hash": "<sha256>"
  },
  "generator": {
    "name": "smart-tree",
    "version": "<semver-or-commit>",
    "parser_versions": {}
  },
  "agent_identity": {
    "kind": "placeholder",
    "id": "local-or-ci-agent",
    "did": null
  },
  "nodes": [],
  "edges": [],
  "summaries": [],
  "tours": [],
  "diff_impact_sets": [],
  "provenance_receipts": [],
  "validation_results": [],
  "policy_status": {
    "state": "warn",
    "checks": []
  }
}
```

## Node taxonomy

Minimum v0 node kinds:

- `repo`
- `directory`
- `file`
- `module`
- `package`
- `service`
- `endpoint`
- `schema`
- `contract`
- `document`
- `workflow`
- `test`
- `config`
- `runtime`
- `policy`
- `domain`
- `concept`

Each node must include:

- stable `id`
- `kind`
- `label`
- optional `path`
- optional `source_anchor`
- `confidence`
- `provenance_receipt_ids`
- `metadata`

Stable IDs must not depend on generation timestamp, traversal order, host path, or agent name. Prefer repo-relative paths and semantic discriminators.

## Edge taxonomy

Minimum v0 edge kinds:

- `contains`
- `imports`
- `depends_on`
- `defines`
- `documents`
- `tests`
- `configures`
- `calls`
- `owns`
- `generates`
- `validates`
- `governed_by`
- `impacted_by`
- `related_to`

Each edge must include:

- stable `id`
- `kind`
- `source`
- `target`
- `confidence`
- `provenance_receipt_ids`
- optional `source_anchor`
- optional `metadata`

## Source anchors

A source anchor identifies where the graph fact came from:

```json
{
  "path": "contracts/example.schema.json",
  "start_line": 1,
  "end_line": 42,
  "content_hash": "sha256:<hash>"
}
```

Graph facts without source anchors must be marked as inferred and carry lower confidence. Inferred graph facts cannot be used as mutation authority.

## Provenance receipts

A provenance receipt records how a claim entered the graph:

- receipt ID
- claim type
- generator or agent
- parser version
- input source hash
- generated time
- confidence
- validation state
- warnings

Receipts are mandatory for generated nodes, generated edges, summaries, tours, and diff impact sets.

## Guided tours

Guided tours are ordered explanations over the graph. v0 requires support for:

- onboarding tour
- architecture tour
- dependency tour
- policy-sensitive tour
- PR impact tour

Tours should reference node and edge IDs, not duplicate free-form claims.

## Diff impact sets

A diff impact set maps a change to affected graph facts:

```json
{
  "id": "diff-impact:<base>..<head>",
  "base": "<git-sha>",
  "head": "<git-sha>",
  "changed_paths": [],
  "affected_nodes": [],
  "affected_edges": [],
  "affected_tests": [],
  "affected_docs": [],
  "affected_policies": [],
  "risk": "low|medium|high|unknown",
  "requires_review": true
}
```

## Policy states

v0 policy states:

- `allow`
- `warn`
- `require_review`
- `deny`
- `unknown`

Missing graph artifacts should default to `warn` or `require_review` in v0, not hard failure across the estate. High-risk paths may still require review under existing branch and security policies.

## Cross-repo responsibilities

`smart-tree` owns structural scanning and deterministic graph emission.

`lampstand` owns local indexing and retrieval over graph artifacts.

`sherlock-search` owns hybrid lexical, semantic-ready, graph-aware, evidence-aware query over repo intelligence.

`ontogenesis` owns ontology, JSON-LD, SHACL-style constraints, and later Avro/TriTRPC generation.

`agent-registry` owns portable agent skill manifests for scan, explain, validate, tour, and PR impact workflows.

`agentplane` owns graph-aware work orders and bounded dispatch context.

`policy-fabric` owns validation gates and policy receipts.

`delivery-excellence` owns freshness, coverage, drift, PR impact, and agent evidence metrics.

`socioprophet` owns the user-facing repo-map / understand workbench.

## v0 acceptance criteria

- A valid fixture artifact exists.
- The artifact validates in CI.
- Scanner output is deterministic for the same commit.
- Search can answer ownership, dependency, test coverage, and PR impact questions from a fixture.
- UI can render a fixture graph with node detail, evidence, and policy state.
- Policy checks distinguish missing, stale, invalid, unanchored, and high-impact artifacts.
- Metrics report freshness, schema validity, provenance coverage, anchor coverage, and PR impact radius.

## Non-goals

- No blind vendoring of third-party codebase graph dashboards.
- No default post-commit hooks without review.
- No local file-serving surface without threat model.
- No autonomous mutation from graph output alone.
- No semantic certainty claims without evidence, confidence, and provenance.

## First implementation tranche

1. Land this platform spec.
2. Add JSON Schema and fixture artifact under platform contracts/examples.
3. Implement Smart Tree emitter or create a direct PR if Issues remain disabled.
4. Ingest fixture through Lampstand.
5. Query fixture through Sherlock.
6. Add Ontogenesis JSON-LD/SHACL mapping.
7. Add Agent Registry skill manifests.
8. Add AgentPlane work-order context fixture.
9. Add Policy Fabric validation decisions.
10. Add Delivery Excellence scorecard.
11. Render fixture in SocioProphet UI.
