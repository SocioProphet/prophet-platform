# Canonical Component Map

**Status:** v0.1 — 2026-06-29
**Purpose:** one source of truth that maps every design-doc vocabulary and every adopted external OSS tool to its **canonical owner** and an explicit **adopt / adapt / observe / isolate** lane. Across the SourceOS/SocioProphet design corpus the same system is described under many names; this document exists to stop *N platforms under N names* drift. The rule is **bind, don't rebuild**.

---

## A. Internal vocabulary reconciliation

Many design docs (Agent-First Node Architecture, Open Agent Archetype, the SourceOS boot/build transcript, the Workspace Control Plane spec) name components that **already exist** in our stack under different words. Canonical owner wins; the doc term becomes an alias.

| Design-doc term(s) | Canonical component | Owning repo | Lane |
|---|---|---|---|
| triRPC, TritRPC, TritRPC(B2/B3), ternary RPC | **TriTRPC** (deterministic ternary-native RPC; receipt_binding v0.1) | `tritrpc` | adopt (the one wire format) |
| Quilt run-package, ledger, provenance spine, run artifacts | **Reasoning-evidence fabric** (ReasoningRun / Event / Receipt / ReplayPlan) | `prophet-platform` (contracts/evidence) | adopt |
| Sentinel, Guardrails, policy engine, egress policy | **Channel-governed runtime gates + Autonomy ladder (L0–L5)** | `prophet-platform` (channel gates, AutonomyAdmissionReceipt) | adopt |
| Loom planner, agentd, Triune Loom, agent kernel/supervisor | **agent-machine loop** (`LoopCtx.autonomyGate`) + `turtle-agentd` | `Noetica` / `agent-machine`, TurtleTerm | adapt |
| AgentEnvelope / Observation / Action / KnowledgeUpdate (Avro) | **Canonical receipts + event envelopes** (ADR-033) | `prophet-platform` (contracts) | adapt (reconcile schemas, don't fork) |
| AtomSpace / Atomese / OpenCog symbolic core | **hellgraph NSR integration** (AtomSpace is reached *through* hellgraph; not a fresh store) | `hellgraph` | adapt |
| Truth substrate / canonical KG | **Reasoning-evidence fabric + authored canon (KKO/KBpedia) + sympy verifier** is system-of-record | `prophet-mesh` / `Noetica` / canon | adopt (authority) |
| Genesis / Bereshit agent / reproducible bootstrap | **Genesis registry** (bind to identity-prime registry genesis) | `prophet-platform/apps/identity-prime` | adopt (see ADR-036) |
| Certified erasure / secure-erase-with-certificate / Proof-of-Emptiness | **Deletion gate upgraded to Proof-of-Emptiness** | `prophet-platform` (ProofOfEmptiness.v0.1 + deletion gate) | adopt (see ADR-036) |
| Capability lattice / ⊥ / capability tokens | **Autonomy ladder formalized as a lattice** (⊗ with strict bottom) | `prophet-platform` | adopt (see ADR-036) |
| ReleaseSet / BootReleaseSet / ExperienceProfile / Fingerprint | **Frozen freeze-pack schemas** (need builder, not redefinition) | `sourceos-workspace`, `SourceOS-Linux__sourceos-boot` | adapt (build the compiler) |
| Lifecycle promotion (draft→…→compliant) | **Katello content-view lifecycle + evidence-gated promote** | `SociOS-Linux__socios` (ansible), gate added 2026-06-29 | adopt |
| Knowledge fabric / Noria-style derived views | **prophet-mesh dual-layer + RAPTOR + HippoRAG retrieval** | `prophet-mesh` | adapt (name the views) |
| LDT-UI / operator console / Mission Board | **GovernSurface / AutonomyPanel** (Noetica) + Agentic GitLab-style shell | `Noetica` | adapt |

**Reconciliation rule:** new code emits onto the canonical component (schema-conformant + evidence-emitting). A doc term never spawns a parallel implementation; it is recorded here as an alias of its canonical owner.

---

## B. External OSS adoption (from `agent_stack_inventory_raci.xlsx`)

Primary tool per capability and its integration rule. License lane governs *how* it may be used.

| Capability | Primary (Accountable) | License | Integration rule |
|---|---|---|---|
| SDLC governance / phase gates / artifact memory | **AIWG** (+ BMad as module) | MIT | Workspace framework; `.aiwg/` artifacts emit onto the evidence fabric (see AIWG assessment) |
| Interactive coding agent | **OpenCode** (Goose secondary) | MIT / Apache-2.0 | Primary runner; AIWG quality gates |
| Multi-agent orchestration / ensemble review | **Gastown** | MIT | Runtime; provenance to fabric + Agent Inbox |
| Persistent memory + retrieval | **Mem0** + `.aiwg/` artifacts | Apache-2.0 | Shared memory substrate; canonical store stays the fabric |
| Browser automation | **Stagehand** | MIT | Expose via MCP |
| OS-level / computer-use automation | **Agent-S** | Apache-2.0 | Controller container, disposable-VM target; **dynamic-validation controller** (P3) |
| App/agent SDK foundation | **Vercel AI SDK** | Apache-2.0 | Within our services; pairs with MCP |
| Knowledge extraction / ontology / KG | **OntoGPT** | BSD-3 | Pipelines → canon/hellgraph |
| Data-access governance | **ZenStack** (app) + Argos (research) | MIT / CC0 | App-layer policy; ReBAC patterns optional |
| Agent task queue / inbox | **Agent Inbox** | MIT | Internal task UI |

### License discipline (isolate / quarantine lanes)
- **Copyleft → isolated network service, never embedded:** Inbox Zero (AGPL-3.0), Zed server components (AGPL). "Don't link it, call it."
- **Restricted / source-available → eval-only or clean-room replace:** Fortemi (BUSL-1.1), Warp (proprietary).
- **Non-standard / high-risk → quarantine + legal review:** AD4M (Cryptographic Autonomy License). Treat as reference/spec source only until reviewed.
- **Permissive (MIT/Apache/BSD/CC0):** adopt freely with notice.

---

## C. Adopt / Adapt / Observe lanes (summary)

- **Adopt now:** TriTRPC, reasoning-evidence fabric, channel-gates + autonomy ladder, Katello evidence-gated promotion, Inception invariants (ADR-036), AIWG, OpenCode, Gastown, Mem0, Agent-S, OTel+OpenInference (P3).
- **Adapt (bind to existing):** agent-machine/turtle-agentd (the "agentd"), canonical receipts (the "AgentEnvelope"), hellgraph (the "AtomSpace"), freeze-pack schemas (need a builder), prophet-mesh retrieval (the "Noria views"), GovernSurface (the operator console).
- **Observe / benchmark:** libp2p/IPFS, Hypercore mesh, Neo4j/Qdrant (only when Postgres+AGE+pgvector is outgrown), LangGraph/AutoGen/CAMEL/CrewAI.
- **Isolate / quarantine:** Inbox Zero, Fortemi, AD4M, Warp.

---

## D. Decisions of record (2026-06-29)

1. **Knowledge substrate:** OpenCog/AtomSpace is reached **through the existing hellgraph + NSR integration**, not stood up fresh. The reasoning-evidence fabric + authored canon remain system-of-record.
2. **Inception Framework invariants adopted now** (genesis registry, certified-erasure Proof-of-Emptiness, capability lattice) — see `adr/ADR-036`.
3. **Semantic Fibration / Ghost space:** formalize the *buildable* substance (Semantic Evidence Chain; epistemology↔ontology hellgraph ops). Hopf/E8/tensor framing stays motivating metaphor — **no derived physics numbers**.

See also: `docs/standards/PROPHET_TRUST_CHAIN_V0.md`, `contracts/AutonomyAdmissionReceipt.v0.1.json`, `adr/ADR-033-canonical-receipts-and-event-envelopes.md`, `adr/ADR-036-inception-strict-initial-invariants.md`.
