# Fog Stack packs

This document records the current Fog Stack pack taxonomy, product-surface intent, and readiness levels inside `prophet-platform`.

## Current parity posture

Fog Stack has reached **credible MVP IBM-style parity** for a local, CI-backed, non-mutating, evidence-based operator proof.

The canonical proof command is:

```bash
make fogstack-parity-readiness
```

The target wraps:

```bash
python3 tools/run_fogstack_parity_readiness.py --summary
```

The command emits:

```text
build/fogstack-local-demo/fogstack-parity-readiness.record.json
```

This parity posture means the local evidence graph proves release, registry, deploy, GitOps, runtime dry-run, Agent Machine node inventory, immutable/declarative update readiness, TurtleTerm/BearBrowser use surfaces, AgentPlane run linkage, and PolicyPlane decision linkage.

It does **not** mean production parity. Live cluster apply, network registry publication, external KMS/HSM-backed signing, production observability, live AgentPlane execution, real GitOps controller reconciliation, and SourceOS/AgentOS live update execution remain post-MVP gaps.

## Decision

Fog Stack should **not** split into separate repositories for AI, Data, Automation, Security, Registry, Runtime, Agent Machine, or Office categories yet.

The shared trust/release/publication/runtime evidence graph is still the dominant implementation concern, and the current pack boundaries do not yet justify independent lifecycles. The right move is to keep engineering in `prophet-platform`, track pack readiness here, and split only when a pack has a clearly independent release cadence, operator lifecycle, support burden, and CI surface.

## Current packs

### Fog Stack Access
- Type: real product surface
- Readiness: 88%
- Repo split now: no
- Why: strongest customer-facing surface. It now has local deploy evidence, GitOps bundle/readiness, runtime dry-run, Agent Machine node inventory, immutable update readiness, AgentPlane linkage, PolicyPlane linkage, and one-command parity validation. Remaining work is live cluster apply, production observability, stronger GitOps controller receipts, and external identity/signing.

### Fog Stack Knowledge
- Type: real product surface
- Readiness: 72%
- Repo split now: no
- Why: clear substrate anchors through knowledge-reason, Lampstand, search, and collaboration adjacency. It is stronger than the earlier estimate, but still composition-heavy and not yet independently packaged.

### Fog Stack Evaluation
- Type: real product surface
- Readiness: 76%
- Repo split now: no
- Why: strong evidence orientation and real eval-fabric substrate. Still more internal platform capability than standalone customer package.

### Fog Stack Security / Trust
- Type: strong shared capability
- Readiness: 90% as platform capability / not yet standalone pack
- Repo split now: no
- Why: the shared trust/release/runtime graph now spans signing evidence, release gates, registry evidence, runtime dry-run safety, AgentPlane, PolicyPlane, and parity readiness. It should remain shared until external KMS/HSM and production identity are integrated.

### Fog Stack Data / GovernAI
- Type: emerging packaging view
- Readiness: 68%
- Repo split now: no
- Why: best treated as a packaging view over Knowledge, Evaluation, Lattice, and GovernAI surfaces. It has meaningful substrate but not enough independent operational lifecycle to split.

### Fog Stack AI / Lattice Runtime
- Type: emerging product surface
- Readiness: 62%
- Repo split now: no
- Why: Lattice/model/prompt/evaluation runtime work makes this stronger than a conceptual future pack, but it is not yet an independently packaged AI product surface.

### Fog Stack Automation / Workflow
- Type: future pack with emerging substrate
- Readiness: 45%
- Repo split now: no
- Why: AgentPlane and PolicyPlane linkage now appears in runtime evidence, but live execution backend, workflow runtime, and production orchestration remain post-MVP.

### Fog Stack Registry / Release Distribution
- Type: shared capability
- Readiness: 78%
- Repo split now: no
- Why: filesystem registry, publication indexes, root metadata, and revocation/rollback evidence make this a strong local shared capability. Network registry publication and external signing identity remain post-MVP.

### Fog Stack Runtime / Agent Machine Node Ops
- Type: shared runtime capability
- Readiness: 72%
- Repo split now: no
- Why: runtime evidence now includes Agent Machine node profile, node inventory, TopoLVM storage posture, immutable update readiness, TurtleTerm/BearBrowser surfaces, AgentPlane run linkage, PolicyPlane decision linkage, and runtime dry-run. Live cluster apply and live AgentPlane execution remain post-MVP.

### Fog Stack Office / Collaboration
- Type: emerging product surface
- Readiness: 58%
- Repo split now: no
- Why: office collaboration runtime, thread history, suggestions, and search adjacency are now real repository surfaces. It is not yet a Fog Stack deployable pack with its own operator lifecycle.

## Repo split triggers

A future Fog Stack pack should not move into its own repository until most of the following are true:

1. it has an independent release cadence
2. it has a distinct operator lifecycle and deployment surface
3. it has dedicated CI/test obligations that reduce, not increase, repo complexity
4. it has support responsibilities distinct from the shared trust/release/runtime substrate
5. the trust/release/runtime graph can be shared without duplicating platform-wide signing, evidence, runtime, and policy logic

## Relationship to `prophet-platform`

`prophet-platform` remains the canonical runtime and deployment substrate.

Fog Stack currently lands here as:
- productization
- conformance
- release metadata
- trust graph
- registry publication
- deployment evidence
- GitOps evidence
- runtime dry-run evidence
- Agent Machine node evidence
- AgentPlane/PolicyPlane linkage
- parity readiness validation
- canonical Makefile target for the MVP parity check

The future packs should therefore be treated as catalog, packaging, and operator-surface views until they are mature enough to justify independent repos.

## Post-MVP gaps

The next work should not pretend the local MVP proof is production parity. Remaining gaps include:

1. live cluster apply with rollback proof
2. network registry publication
3. external KMS/HSM-backed signing and approval identity
4. live AgentPlane execution backend
5. stronger GitOps controller reconciliation receipts
6. production observability and alerting
7. TopoLVM live cluster integration
8. Nix/ostree update execution receipts for SourceOS/AgentOS
9. operator UX consolidation and reusable evidence rendering modules
