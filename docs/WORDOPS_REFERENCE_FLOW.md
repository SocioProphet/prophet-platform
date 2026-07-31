# WordOps Reference Flow — Incident → Containment

This is the estate realization of the Phase-0 reference pack's implementation-order
step 10 ("first reference flow"). It threads a real incident from a public Matrix
room to a governed, audited endpoint-containment action, using components that now
exist in this repo.

Governing rule (from the reference pack, kept verbatim in spirit): **Matrix rooms
are collaboration context, not the authorization ledger.** The authorization
decision and its durable receipt live at the gateway and the ledger — never in a
room.

## Components (all in-repo)

| Role | Component | Status |
|---|---|---|
| Public edge + private core Matrix estates | `infra/k8s/wordops-matrix/`, `infra/wordops/matrix/` | ✅ deployed (#1156) |
| Case kernel (durable orchestration outside MCP) | `apps/matrix-qes-operator/` | ✅ present |
| Autonomy classes A0–A4 | `docs/WORDOPS_APPROVAL_TO_LEASE_GOVERNANCE.md` | ✅ present |
| Lease issuance/action policy | `infra/wordops/opa/lease_policy.rego` | ✅ new, `opa test` green (14/14) |
| Canonical lease record / wire token | `schemas/wordops/capability-lease.schema.json` · `…-token.schema.json` | ✅ record + ✅ new token |
| Lease-enforcing MCP gateway | `apps/wordops-mcp-gateway/` | ✅ new, `go test` green |
| Containment / blast-radius engine | `apps/gbrg-containment/` (Go front door for `gbrg-core::containment`) | ✅ present |
| Executions ledger (durable receipt sink) | `apps/agent-activity-ledger/` (`POST /executions`) | ✅ new POST + teeth |
| Containment agent cards | `apps/wordops-mcp-gateway/a2a/{public,extended}-agent-card.json` | ✅ new |

## The flow

1. **Public intake** — a report lands in `#welcome:public.socioprophet.ai` (federation on,
   encryption off, no regulated details). The public agent card exposes only
   read-only/discovery skills.
2. **Human handoff** — an operator triages in `#support-lobby` and, if a real threat,
   opens a **private case/incident room** `#incident-<id>:ops.socioprophet.ai`
   (encryption on, invite-only, federation off), created by the room-factory service
   account. Case state changes mirror to the **case kernel** (`matrix-qes-operator`).
3. **Lease request** — to isolate an endpoint, the incident commander requests a
   capability from the broker. A sever is **intrinsically A4** (urgent containment):
   the broker calls OPA `allow_issue`, which requires a responder/IC role, an
   `approval_id` **or** a documented break-glass ref, satisfied step-up, and the
   **shortest TTL (≤30s)**. On allow, the broker mints a down-scoped
   **capability-lease token** (audience `mcp://gbrg-containment`, scope
   `containment:sever:full|selective`, bound to `case_id` + `task_id`).
4. **Controlled MCP action** — the agent calls `POST /mcp/invoke` on the
   **wordops-mcp-gateway** with the lease + tool. The gateway enforces
   audience/scope/case/task/expiry and re-asserts *containment ⇒ A4*. On allow it
   calls `gbrg-containment`, receives a `ContainmentProofArtifact`, and maps it
   **honestly**: a no-op sever (INCONCLUSIVE / `speculative`) is `pending`, never a
   verified containment.
5. **Durable receipt** — the gateway writes an **ExecutionReceipt** (conforming to
   `prophet-core-contracts`) to the **ledger**. The ledger rejects self-contradictory
   receipts (INV1–INV4). A **denied** attempt is *also* written (A4 is heavily
   audited — teeth fire both ways).
6. **Room summary** — only a room-safe summary returns to `#incident-<id>` (verdict +
   `receipt_hash` + contained/residual counts). The warrant itself is in the ledger,
   surfaced in the cockpit's Executions Ledger — not pasted into the room.

## Sequence

```mermaid
sequenceDiagram
    participant R as #incident room
    participant B as Capability broker (OPA allow_issue)
    participant G as wordops-mcp-gateway (allow_action)
    participant C as gbrg-containment
    participant L as agent-activity-ledger
    R->>B: request A4 lease (containment:sever, case+task, approval/break-glass)
    B-->>R: capability-lease token (≤30s, audience-bound) or DENY
    R->>G: POST /mcp/invoke {lease, tool: sever_endpoint}
    G->>G: authorize (audience/scope/case/task/expiry; containment⇒A4)
    alt admitted
        G->>C: GET /containment?scope=full|selective
        C-->>G: ContainmentProofArtifact (epistemicLevel, contained/residual)
        G->>L: POST /executions (allow; verified|pending)
        G-->>R: summary + receipt_hash
    else denied
        G->>L: POST /executions (block/denied) — audited
        G-->>R: 403 + reason + receipt_hash
    end
```

## Maturity / honesty

- ✅ **Real + tested now:** the OPA policy (A0–A4), the gateway lease enforcement and
  fail-closed denial audit, the containment call, the ExecutionReceipt emission, and
  the ledger's invariant checks — all covered by `opa test` and `go test`.
- 🟡 **Interface / fixture:** `gbrg-containment` computes over a fixture topology
  (the authoritative algorithm is `gbrg-core::containment` in sociosphere); the
  ledger store is in-memory. Both are documented as follow-ons in their own headers.
- ⬜ **Next increment:** the room-factory service (Synapse admin API) and broker
  token-exchange service are specified here and by the OPA policy + token schema, but
  are not yet live services in this PR — they are the next step, wired to the same
  contracts so no interface churn.
