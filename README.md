# Prophet Platform (SocioProphet)

This repository is the **runtime and deployment hub** for the SocioProphet platform.

It is intentionally a **thin platform monorepo**:
- `apps/` contains deployable services (API, gateway, web portal, search/index daemons, execution services)
- `contracts/` contains platform-facing event, evidence, and receipt contracts consumed by runtime services
- `docs/` contains platform-level guidance (architecture, transport binding, security, roadmap)
- `infra/` contains deployment wiring (Kustomize, Argo CD appsets, namespaces, etc.)
- `tools/` contains validation and smoke-test helpers (`standards.lock.yaml` gates platform drift checks)
- `libs/` contains small shared runtime bindings that adapt pinned upstream standards into platform code

---

## Legend

*The world needed a floor before anything could be built on it.*

### Turtle Island — Sky Woman, Muskrat, and the Great Turtle

In the beginning there is only sky and water.  There is no land.

**Sky Woman** falls from the Sky World above — cast out, or choosing to fall,
depending on the telling.  She plummets toward the water.  The animals of the
water world look up and see her coming.  They do not flee.  They convene.  The
**Geese** break her fall, carrying her on their wings so she does not strike the
water dead.  But she still needs ground.

The creatures of the deep discuss what she will need: earth.  One by one they
dive, seeking mud from the bottom of the water.  The Otter tries and fails.  The
Beaver tries and fails.  Great and capable animals turn back, unable to reach
the bottom.

Then the **Muskrat** — small, often overlooked — volunteers.  It dives past
where the others turned back.  It keeps going.  In some tellings it returns dead,
its lungs spent, but its paw still clenched around a handful of mud.  The mud
exists.  The sacrifice made ground possible.

That mud is placed on the back of the **Great Turtle**, who volunteered to be
the carrier.  Sky Woman breathes on it, walks in a circle, tends it with care.
The earth grows.  It grows until it becomes a continent — **Turtle Island** —
the land that rests on the back of a great Turtle who never stopped carrying it.

This story is told among the **Lenape** (leh-NAH-pay) — the Delaware people —
and among the **Haudenosaunee Confederacy** and other nations across what is
now called North America.  *Lenape* means **"real people"** or **"original
people"**: not first in a sequence, but people who are genuinely, fully
themselves.  People of the ground.

> *We tell this legend with respect, not with claim.  The Lenape Nation,
> the Lenape Nation of Pennsylvania, and the Haudenosaunee Confederacy are
> the living holders of this tradition.  We draw only from what they have
> chosen to share publicly.  We do not represent ceremony, inner teaching,
> or knowledge not offered for general understanding.  Go to the source:
> delawarenation-nsn.gov; lenape-nation-pa.org; haudenosauneeconfederacy.ca.*

---

### Sophia — Wisdom That Descends and Becomes Ground

In the **Gnostic tradition** — texts preserved in the **Nag Hammadi library**,
discovered in Egypt in 1945 and publicly available — **Sophia** (Greek:
Σοφία, "Wisdom") is the last and youngest emanation of the divine **pleroma**:
the fullness of light from which all creation comes.

She acts without her consort.  She **falls**.

Her descent is not simply error.  It is the act that makes a grounded world
possible.  In falling she becomes the matter from which the world is shaped.
She is wisdom consenting to become foundation — the knowing that agrees to be
the floor on which all things stand.  She waits for the work of restoration
while being, in the meantime, the ground itself.

The parallel to Sky Woman is not accidental:
- Both fall from a high realm to a lower one.
- Both become, in their falling, the precondition for the earth.
- What descends does not die.  It becomes the carrier of everything built above.

---

### Anu — The Sky from Which Things Fall

In the **Sumerian and Akkadian traditions** — cuneiform texts among the oldest
written records of human thought, including the **Enuma Elish** (the Babylonian
creation epic) and the **Atrahasis** — **Anu** (An in Sumerian) is the
**sky god**: the highest heaven, the unmoved vault above, the origin of divine
authority, the source from which everything descends.

Sky Woman comes from a world above the water.  Sophia emanates from the pleroma.
Both descend from something that is, in its function, Anu-like: the **original,
uncreated height** from which everything that becomes ground must first fall.

Anu does not fall.  He **is what is fallen from**.  He is the condition of
distance that makes descent possible — and therefore the condition that makes
ground possible.

---

### The Pattern

> **Sky (Anu) → Fall (Sky Woman / Sophia) → Patient Carrier (Turtle) → Growing Earth (Turtle Island / the world)**

The sky is the source: complete, beyond reach on its own terms.

The fall is not catastrophe.  It is how the sky enters the world — transformed
by the willingness to descend, to be carried, to become ground.

The patient carrier — Turtle, matter, the earth itself — holds what arrives.
It does not need to understand.  It holds.

And the world grows from the mud held in the paw of the one willing to dive
deepest.

---

### The Control Plane as Turtle's Back

This repository is a governance layer — the floor on which agentic work stands.
The metaphor is not decorative.

| Layer | Legendary parallel |
|---|---|
| **Evidence** (claim extraction, memory store) | The ground itself — Turtle's back; what Muskrat brought up from the deep |
| **Policy gate** | The sky — sets conditions; judges what evidence is sufficient |
| **Claims** | The world growing on the ground — accumulating, contradicting, confirming |
| **Consensus Arbitrator** | The question: *Is this earth?  Can we stand here?* |
| **Temporal Outbox** | The Turtle's consent — stable, load-bearing, carrying without needing to understand |

See also: [`LEGEND.md`](./LEGEND.md) — the full legend in extended form.

---

## Why this repo exists

Standards and governance stay in dedicated upstream repositories. `prophet-platform` is where those standards become running services, concrete deployment topologies, and platform contracts.

## Quickstart

```bash
make validate
make validate-workroom-update-contract
make validate-professional-intelligence-manifest
make validate-svf-agent-contract
make validate-environment-validate-change-v2
make validate-trust-chain-contracts
make validate-channel-runtime-gates
make smoke-health
```

## Reading order

1. `docs/ARCHITECTURE.md`
2. `docs/TRITRPC_SPEC.md`
3. `docs/TRITRPC_PLATFORM_BINDING.md`
4. `professional-intelligence.manifest.yaml`
5. `docs/WORKROOM_UPDATE_RUNTIME_BOUNDARY.md`
6. `docs/PLATFORM_EVAL_FABRIC.md`
7. `docs/SVF_VALIDATE_CHANGE_AGENT_CONTRACT.md`
8. `docs/standards/PROPHET_TRUST_CHAIN_V0.md`
9. `docs/TRUST_CHAIN_ADMISSION_CONTRACT.md`
10. `docs/standards/PROPHET_TRUST_CHAIN_IMPLEMENTATION_MAP.md`
11. `docs/CHANNEL_GOVERNED_RUNTIME_GATES.md`
12. `contracts/`
13. `infra/k8s/`

## Professional Intelligence manifest

`professional-intelligence.manifest.yaml` is the platform-side cross-repo alignment manifest for Professional Intelligence OS. It records runtime/platform ownership while pointing to upstream product, workspace, policy, model, topic, memory, receipt, and estate-ledger authority surfaces.

The `workspaceOS` lane is currently `contract-aligned`: Professional Workroom schema, example, validator, Sociosphere topology, workspace-inventory overlay, and systems-learning receipt exist. This does not imply runtime implementation or demo readiness.

Relevant files:

- `professional-intelligence.manifest.yaml`
- `tools/validate_professional_intelligence_manifest.py`

Validate locally:

```bash
make validate-professional-intelligence-manifest
```

Boundary: contract alignment does not imply runtime implementation. Runtime implementation does not imply demo readiness without evidence and adoption telemetry. Prophet Workspace owns workroom product semantics; Prophet Platform owns runtime deployment and service composition.

## Workroom update contract

Prophet Platform now carries a minimal workroom update request/response contract lane for Professional Workroom substrate refs. This is a no-runtime, no-network contract layer: it validates the shape and boundary of a request to attach recovered-substrate refs to a workroom surface, but it does not mutate live workroom state.

Relevant files:

- `docs/WORKROOM_UPDATE_RUNTIME_BOUNDARY.md`
- `contracts/workspace/workroom-update-request.example.json`
- `contracts/workspace/workroom-update-response.accepted.example.json`
- `contracts/workspace/workroom-update-response.invalid-runtime-mutation.example.json`
- `tools/validate_workroom_update_contract.py`

Validate locally:

```bash
make validate-workroom-update-contract
```

Boundary: `accepted_for_review` is not execution. The accepted-response fixture requires `runtimeMutationPerformed: false`; the invalid mutation fixture proves that `runtimeMutationPerformed: true` under `accepted_for_review` is rejected. Runtime implementation requires a separate platform service contract, persistence model, policy gate, receipt path, and the runtime prerequisites in `docs/WORKROOM_UPDATE_RUNTIME_BOUNDARY.md`.

## Sovereign Validation Fabric agent contract

Prophet Platform owns the agent-facing `validate_change` contract for Sovereign Validation Fabric. The first tranche is read-only and selection-oriented: it validates request, selected-plan response, and PR-readiness summary fixtures without executing Actions, issuing receipts, or granting agent autonomy.

Relevant files:

- `docs/SVF_VALIDATE_CHANGE_AGENT_CONTRACT.md`
- `contracts/svf/validate-change-request.example.json`
- `contracts/svf/validate-change-response.example.json`
- `contracts/svf/pr-readiness-summary.example.json`
- `tools/validate_svf_agent_contract.py`

Validate locally:

```bash
make validate-svf-agent-contract
```

## Environment validation / `validate_change` v2

Prophet Platform also carries the first environment-validation request surface for the Signadot-parity bridge. This is the product/runtime contract layer: it accepts a change, references Sociosphere workspace/environment state, requests AgentPlane synthetic execution, and returns environment status plus evidence references.

Relevant files:

- `contracts/environment/validate-change-v2-request.example.json`
- `contracts/environment/validate-change-v2-response.environment-requested.json`
- `contracts/environment/validate-change-v2-response.environment-observed.json`
- `contracts/environment/validate-change-v2-response.environment-failed.json`
- `tools/validate_environment_validate_change_v2.py`

Validate locally:

```bash
make validate-environment-validate-change-v2
```

Boundary: this is still a synthetic/no-network contract layer. It does not create live infrastructure, route traffic, isolate queues, isolate stateful resources, or certify Signadot-style runtime parity. AgentPlane owns execution/evidence. Sociosphere owns workspace/environment state. Prophet Platform owns this product/API invocation contract.

## Prophet Trust Chain

Prophet Platform now carries the cross-repo **Prophet Trust Chain v0** standard map, the implementation tracker, the platform `admit_artifact` contract specification, and the first platform-side `admit_artifact` contract fixtures.

Prophet Trust Chain maps SocioProphet to the Lightwell-class enterprise open-source security pattern while preserving our broader boundary: package and runtime evidence are necessary, but enterprise AI admission also requires model, dataset, agent, tool, workflow, policy, execution, receipt, remediation, rollback, revocation, and learning evidence.

Relevant files:

- `docs/standards/PROPHET_TRUST_CHAIN_V0.md`
- `docs/TRUST_CHAIN_ADMISSION_CONTRACT.md`
- `docs/standards/PROPHET_TRUST_CHAIN_IMPLEMENTATION_MAP.md`
- `contracts/trust-chain/admit-artifact-request.example.json`
- `contracts/trust-chain/admit-artifact-response.allowed.example.json`
- `contracts/trust-chain/admit-artifact-response.denied.example.json`
- `tools/validate_trust_chain_contracts.py`

Validate locally:

```bash
make validate-trust-chain-contracts
```

Boundary: this is a platform contract and standard-map lane. It does not claim IBM/Red Hat Lightwell integration, live scanner integration, or production certification from fixtures alone. The allowed fixture is scoped evidence composition; the denied fixture proves fail-closed production-admission behavior when blocking risk or missing verified replay exists.

## Channel-governed runtime gates

Prophet Platform now carries the first runtime-gate contract for channel-conditioned observations. This is the platform-side consumer of ProCybernetica Reciprocal Channel Governance, Ontogenesis `rcg:`, Memory Mesh channel provenance write gates, Regis epistemic edge records, and HolographMe projection-loss profiles.

Relevant files:

- `docs/CHANNEL_GOVERNED_RUNTIME_GATES.md`
- `contracts/channel-governance/runtime-gate.candidate-memory.example.json`
- `contracts/channel-governance/runtime-gate.confirmed-memory.rejected.example.json`
- `tools/validate_channel_runtime_gates.py`

Validate locally:

```bash
make validate-channel-runtime-gates
```

The candidate-memory fixture is expected to pass. The confirmed-memory fixture is expected to fail semantically because an ASR-conditioned percept attempts a confirmed-memory sink that is disallowed by the advisory channel envelope and lacks required repair posture.

Boundary: this is a contract and validator lane only. It does not add production middleware, broker policy, database schema, or API endpoint behavior.

## Evaluation fabric lane

The platform also carries a first-class **evaluation, observability, and competition-intelligence lane**.

Start here:
- `docs/PLATFORM_EVAL_FABRIC.md`
- `docs/LOCAL_DEV_EVAL_FABRIC.md`
- `docs/EVAL_FABRIC_GOVERNANCE.md`
- `apps/eval-fabric-api/`
- `schemas/eval/`
- `infra/local/docker-compose.eval-fabric.yml`

This lane is platform responsibility, not a detached benchmark pack. It owns the container, datastore, schema, and API bootstrap for platform-level ranking, replay, and intelligence work.

## Notes on this phase

This phase removes the plaintext `PING/PONG` bootstrap path and replaces it with a minimal **TriTRPC v1** runtime binding for internal service health traffic. The upstream `SocioProphet/TriTRPC` repository remains the normative transport source of truth; this repository only defines the platform-specific stream binding and deployment profile around that standard.
