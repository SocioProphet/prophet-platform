# Fog Stack status and roadmap

This document captures the current state of Fog Stack work inside `prophet-platform`.

## Repository role

`prophet-platform` is the runtime and deployment substrate for platform services. Fog Stack lands here as the productization, conformance, release, publication, deployment, runtime-evidence, and trust layer for deployable offerings built on that substrate.

## Current parity posture

Fog Stack has reached **credible MVP IBM-style parity** inside `prophet-platform`.

This means the repository now has a single local evidence path that proves a deployable Fog Stack Access candidate across release, registry, deploy, GitOps, runtime dry-run, Agent Machine node substrate, immutable/declarative update readiness, AgentPlane linkage, PolicyPlane decision linkage, and operator-facing evidence.

This does **not** mean production parity. The MVP parity claim is bounded to local, contract-backed, non-mutating, CI-proven evidence. Live cluster mutation, external KMS/HSM signing, production observability, network registry publication, and live AgentPlane execution remain post-MVP work.

The canonical one-command MVP parity check is:

```bash
make fogstack-parity-readiness
```

The target wraps:

```bash
python3 tools/run_fogstack_parity_readiness.py --summary
```

It emits:

```text
build/fogstack-local-demo/fogstack-parity-readiness.record.json
```

The readiness checker validates the full local demo evidence graph, artifact-index digest integrity, and MVP-critical runtime safety invariants.

## Repository strategy decision

Fog Stack should **not** split into separate repositories for AI, Data, Automation, Security, Registry, Agent Machine, or node-operation categories yet.

At the current stage, the trust/release/publication/runtime-evidence machinery is still highly shared across all surfaces. Splitting now would mostly increase coordination overhead and fragment the release/trust/runtime graph before those categories have clearly independent lifecycles.

The correct near-term move is:
- keep the engineering and trust/release/publication/runtime evidence machinery in `prophet-platform`
- track future pack categories here as product surfaces and readiness states
- split into separate repos only when a pack has an independently justified lifecycle, release cadence, operator surface, and support burden

See also:
- `docs/FOGSTACK_PACKS.md`
- `catalog/fogstack-packs-v0.1.yaml`

## Merged offering slices

The following initial offering slices are already merged into `main`:

- **Fog Stack Access** — initial upstream offering slice via PR #25
- **Fog Stack Knowledge** — governed ingress + local daemon offering slice via PR #26
- **Fog Stack Evaluation** — evaluation fabric offering slice via PR #27

## Merged validation, release, and runtime slices

The following supporting slices are already merged into `main`:

- native validator/helper surfaces and initial Access bundle/rulepack
- release metadata refresh via PR #41
- release schemas and validation execution criteria via PR #42
- CI-oriented validation-record emitter via PR #48
- native `Makefile` validation hook refresh via PR #51
- signed-manifest attachment helper via PR #52
- signed-manifest verification helper via PR #58
- signature trust evidence record via PR #62
- release evidence index via PR #63
- artifact backlinking via PR #68
- cryptographic signature verification record via PR #76
- external signature verification input normalization via PR #93
- external signature verification runner via PR #134
- release sealing via PR #136
- release seal signature support via PR #143
- release seal cryptographic verification record via PR #148
- release seal verification runner via PR #151
- release seal artifact linking via PR #153
- release proof pipeline runner via PR #159
- release proof CI workflow via PR #160
- wider release graph linking via PR #161 and refreshed follow-up PR #165
- wider release graph CI workflow via PR #163
- openssl-backed release proof verification via PR #164
- wider release proof pipeline runner via PR #167
- canonical manifest digest refresh and CI enforcement via PR #169
- manifest publication path via PR #171
- manifest promotion path via PR #175
- manifest promotion policy enforcement via PR #200
- manifest promotion approval enforcement via PR #202
- manifest promotion approval cryptographic verification via PR #207
- release publication gate via PR #211
- registry publication index via PR #212
- filesystem registry adapter via PR #215
- registry root metadata and revocation/rollback index support
- local demo deploy-plan generation
- Kubernetes manifest rendering and cluster-readiness dry-run records
- GitOps bundle generation, checking, and readiness records
- local cluster runtime adapter and runtime dry-run records
- Agent Machine node profile, TurtleTerm, and BearBrowser use-surface contracts
- AgentPlane run linkage in runtime evidence
- PolicyPlane decision linkage in runtime evidence
- immutable/declarative update readiness records
- Agent Machine node inventory records
- full local demo evidence indexing and operator summaries
- parity readiness checker and one-command parity runner
- `make fogstack-parity-readiness` canonical operator target

## Current active frontier

Fog Stack is now past initial release-publication hardening and has entered **MVP runtime evidence closure**.

The current local MVP parity path is:

1. validate bundles and rulepacks
2. emit validation records
3. refresh canonical manifest digests
4. build a manifest publication set
5. promote the publication set through policy
6. require approval and approval-signature verification
7. emit a release publication gate record
8. build a registry publication index
9. publish the gated index and referenced artifacts to a filesystem registry layout
10. build local deploy-plan evidence for `fogstack.access`
11. render Kubernetes manifests
12. emit cluster-readiness dry-run records
13. build and check GitOps bundle artifacts
14. emit GitOps readiness records
15. build Agent Machine node profile evidence
16. prove TurtleTerm and BearBrowser as first-class governed use surfaces
17. emit immutable/declarative update readiness records
18. emit Agent Machine node inventory records including TopoLVM storage posture
19. build a local cluster runtime adapter
20. emit non-mutating runtime dry-run evidence
21. bind runtime dry-run evidence to AgentPlane run context
22. bind runtime dry-run evidence to PolicyPlane decision context
23. index all MVP-critical artifacts in the full local demo
24. emit one consolidated FogStack parity readiness record
25. expose the parity proof through a canonical Makefile target

## Product-pack readiness matrix

The detailed matrix and pack taxonomy live in:
- `docs/FOGSTACK_PACKS.md`
- `catalog/fogstack-packs-v0.1.yaml`

## Current trust/publication/runtime graph shape

The release/trust/publication/runtime graph now consists of these machine-readable artifacts:

- release manifest
- validation record
- signature verification record
- signature trust record
- cryptographic signature verification record
- release evidence index
- release seal
- release seal signature metadata
- release seal cryptographic verification record
- release proof pipeline outputs
- wider release graph links
- manifest publication set
- promoted manifest publication set
- promotion policy record/check result
- promotion approval record
- promotion approval cryptographic verification record
- release publication gate record
- registry publication index
- filesystem registry publication/check artifacts
- Agent Machine node profile
- Agent Machine node inventory record
- immutable/declarative update readiness record
- deploy plan
- Kubernetes manifests
- Kubernetes manifest check record
- cluster-readiness record
- GitOps bundle
- GitOps Application
- GitOps Kustomization
- GitOps readiness record
- local cluster runtime adapter
- runtime dry-run record
- AgentPlane run linkage
- PolicyPlane decision linkage
- local demo artifact index
- parity readiness record
- Makefile parity-readiness target

## Known post-MVP gaps

The next tranches should focus on:

1. **Live cluster apply path** guarded by AgentPlane and PolicyPlane, including explicit human approval and rollback proof.
2. **Network registry publication** beyond filesystem registry export.
3. **External KMS/HSM integration** for release identity, signing keys, and runtime approval identities.
4. **Live AgentPlane execution backend** rather than local script-driven evidence only.
5. **Stronger GitOps controller integration** with a real controller reconciliation receipt, not only generated Application/Kustomization artifacts.
6. **Production observability** for runtime, deployment, GitOps reconciliation, node inventory drift, and policy decisions.
7. **TopoLVM live cluster integration** beyond node-profile and inventory evidence.
8. **Immutable update execution path** for SourceOS/AgentOS, including real Nix/ostree update preflight, staging, rollback, and audit receipts.
9. **Operator UX consolidation** so local-demo evidence renderers are decomposed into reusable modules instead of several ad hoc updaters.
10. **Status and registry docs kept current** whenever publication gates, runtime surfaces, or registry adapters land.

## Position in the maturity ladder

Fog Stack in `prophet-platform` is now at **credible MVP IBM-style parity** for local, evidence-backed, non-mutating operator proof.

It has moved from offering taxonomy and local trust records into gated, CI-backed, registry-ready, runtime-evidenced, AgentPlane/PolicyPlane-linked artifact surfaces. The immediate risk is now not lack of proof, but overclaiming production readiness before live cluster execution, production observability, external identity/signing, and network registry publication are complete.
