# Agent-OS Node Binding

**Status:** v0.1 — 2026-06-29
**Purpose:** bind the *Agent-First Node Architecture* and *Open Agent Archetype* design docs to components that already exist, so the node story is implemented by **binding, not rebuilding**. This is the node-level companion to [CANONICAL_COMPONENT_MAP.md](CANONICAL_COMPONENT_MAP.md); precedence and aliases there apply here.

## Principle

Both node docs describe one machine: an OS-native agent supervisor with a symbolic core, an on-node small model, contract-driven messaging, and tiered placement (host → LMS → mesh → cloud). Every load-bearing piece maps to something we run. Net-new work is confined to the genuine seams listed at the end.

## Binding table

| Node-doc component | Canonical implementation | Binding action |
|---|---|---|
| `agentd` / agent kernel / supervisor / Triune Loom / Loom planner | **agent-machine loop** (`LoopCtx.autonomyGate`, server.ts tool→level policy) + `turtle-agentd` | The node runner is agent-machine; do not write a new supervisor. Planner = the existing tool loop. |
| `agentctl` CLI | TurtleTerm / agent-machine CLI surface | Add node verbs (`send`/`offload`/`ask`) as thin wrappers over existing tool calls. |
| ToolBus (AgentMessages over NATS/MQTT/UDS) | **TriTRPC** (UDS same-host, authenticated frames cross-pod) | One wire format. AgentMessage = a TriTRPC-carried envelope. |
| `AgentEnvelope` / `Observation` / `Action` / `KnowledgeUpdate` / `LLMRequest`/`Response` (Avro) | **Canonical receipts + event envelopes** (ADR-033) + reasoning-evidence Event/Receipt | Reconcile the Avro records to the canonical receipt schema family; keep Avro as a transport encoding, not a second data model. `Action` capability checks = autonomy ladder + channel-gate sinks. |
| Guardrails / Sentinel (capability enforcement, PII, egress) | **Channel-governed runtime gates + autonomy ladder (L0–L5)** | Guardrails are the gates; capability tokens compose on the lattice (ADR-036, strict bottom ⊥). |
| Memory Fabric — User Graph / System Graph (AtomSpace) | **hellgraph NSR** (AtomSpace reached through hellgraph) + reasoning-evidence fabric + authored canon (authority) | User/System graphs are hellgraph workspaces; promotion to canon is governed (epistemology↔ontology spec, hellgraph doc 08). |
| Vector Index (FAISS/Milvus-lite) / RAG | **prophet-mesh** dual-layer + RAPTOR + HippoRAG retrieval | Bind; don't stand up a parallel index. |
| LLM Service (on-node SMLL; bigger in LMS/fog) | Noetica agent-machine + Ollama (NOETICA_AM_PORT) | Existing on-node model service; tiering = placement policy below. |
| Secret & Consent (Vault/keychain + append-only consent ledger) | Secrets door + reasoning-evidence ledger; **certified erasure = Proof-of-Emptiness** (ADR-036) | Consent/erase events are receipts; deletion is PoE-gated. |
| Provenance spine — Ledger + Quilt run-package | **Reasoning-evidence fabric** (ReasoningRun/Event/Receipt/ReplayPlan) | The run-package is a replay bundle; Quilt is an alias. |
| Placement / tier selection (host → LMS k3s → edge → fog → cloud) | prophet-mesh / sociosphere **lattice-placement-spine** + the Image-Gen corpus cost-vector model | Reuse the placement engine; the node "Planner" calls it. |
| Avro + JSON-LD `@context` semantic stability | canon + KKO/KBpedia alignment | JSON-LD contexts resolve to canon IRIs. |
| Observability of node hops | **OTel + OpenInference** (just landed) | Each agentd hop is a span correlated to its receipt (`prophet.reasoning_run.id`). |
| Isolation dial (container / VM / Kata / microVM mesh) | SourceOS isolation profiles + Firecracker/gVisor (P-future) | Node selects an isolation profile; enforcement is the sandbox-staging gap (tracked separately). |

## Genuine net-new seams (the only things to actually build)

1. **agentctl node verbs** — thin CLI wrappers (`send`/`offload`/`ask --tools …`) over agent-machine tool calls + the placement engine. No new runtime.
2. **Avro↔receipt codec** — a small adapter so AgentEnvelope/Observation/Action serialize to/from the canonical receipt schema (transport encoding only).
3. **System Graph collectors** — the Network/Connections and Terminal/Shell agents' OS observers (sockets/proc/pcap → hellgraph System Graph), policy-gated and emitting receipts. This is the one genuinely new agent behavior; everything it produces flows onto existing contracts.

Everything else in the two node docs is an alias of a shipped component. Do not fork the supervisor, the wire format, the memory substrate, the gates, or the provenance spine.

## References
- [CANONICAL_COMPONENT_MAP.md](CANONICAL_COMPONENT_MAP.md), `adr/ADR-033-…`, `adr/ADR-036-…`, `docs/CHANNEL_GOVERNED_RUNTIME_GATES.md`, `docs/OBSERVABILITY_OTEL_OPENINFERENCE.md`
- hellgraph `docs/specs/08_Reflexive_Loop_and_Convergence_v0_1.md` (epistemology↔ontology)
