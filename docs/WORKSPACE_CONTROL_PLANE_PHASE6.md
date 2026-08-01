# Workspace Control Plane — Phase 6 (overlay transport)

Implements **Phase 6**: a private-mesh overlay for approved topics (D8/D10),
scaffold-first. The durable Hypercore/Autobase **semantics** are implemented
in-process with **no network / no Hyper-stack dependency**; the real stack swaps
in behind the same `OverlayBroker` interface later.

## Pattern registry semantics (§5)

- **AppendLog** — single-writer, append-only, blake2b **hash-chained** log
  (Hypercore); `verify()` is tamper-evident.
- **sparse_fetch** — lazy subset fetch by index (`seed_sparse`).
- **linearize** — merge multiple writer logs into one **causal, deterministic**
  view by `(lamport clock, writer, seq)`, so peers converge (`linearize_multiwriter`,
  Autobase).
- **OverlayBroker.join** — `join_topic_or_peer`: a topic is joined **only after a
  trust decision** (D9). Refuses `untrusted` / `revoked` / `expired` /
  `unknown_transport`; append/fetch/linearize are gated on membership.

## Trust wiring

`join(manifest, trusted=..., now=...)` takes the trust verdict as an explicit
argument — the caller passes `TrustBroker.verify_manifest(...).trusted` (Phase 5),
keeping the discovery, trust, and transport planes separate (D8).

## Validation

`tools/tests/test_overlay_transport.py` — 7 tests: chain + tamper, sparse subset,
causal linearization (order-independent), the four join refusals, join →
append/fetch/linearize, unjoined refused, and topic-manifest conformance.
Path-filtered CI: `.github/workflows/control-plane-overlay.yml`.

## Next (Phase 7)

Temporal outbox + approvals + workflow replay over `workflow-run.v0` (needs
Temporal infra → scaffold-first: durable outbox state machine + approval gate).
