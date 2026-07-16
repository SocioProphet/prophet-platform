# Open-Chat Commons Aggregator — Design V0

**Status:** spec / proposed. Unblocks the SearXNG unification (task #5) for the opt-in open-chat commons.
**Companion:** Noetica PR #483 shipped the per-instance, PII-gated mechanism (gate → redacted index → `/api/open-chats/search`). This doc specs the **shared aggregator** that makes it genuinely *community-wide* and reachable by SearXNG in-cluster.

---

## 1. The problem this solves

PR #483 gives each Noetica instance a local, redacted, searchable index of its own open chats. That is safe and complete **per instance**, but two things are missing for the killer feature:

1. **Community-wide reach.** An open chat should be findable by *any* user's agent, not just its author's. That needs a corpus aggregated across instances.
2. **SearXNG can't reach it.** SearXNG runs in-cluster (`socioprophet` ns); the Noetica agent-machine is a local/desktop process. A SearXNG `json_engine` needs a reachable in-cluster `search_url`. Wiring it at a non-existent endpoint is the "deployment references something that doesn't exist" anti-pattern (`docs`… deploy-hygiene). So we deploy a real endpoint first.

---

## 2. The one invariant that cannot bend

**Redaction happens LOCALLY, before anything leaves the author's device. The aggregator never receives raw chat text — only the already-redacted snapshot.**

`open-chat-gate.ts` (redact.ts + egress-hygiene.ts, mapping discarded, fails closed) runs at the local agent-machine at publish time, exactly as today. The federation transports the *output* of the gate, never the input. Corollary: even a fully-compromised aggregator leaks no un-redacted PII, because it never held any.

**Belt-and-suspenders:** the aggregator re-runs the *floor* gate on ingest (no user policy, just the deterministic PII/exfil pass). This defends the commons against a **rogue or buggy instance** that publishes under-redacted text. The gate is cheap and idempotent (masking already-masked text is a no-op), so running it twice costs nothing and closes the "trust every publishing node" hole.

---

## 3. Architecture

```
┌─ Noetica instance (local, per user) ─────────────┐
│  chat → gateOpenChat() [AUTHORITATIVE redaction]  │
│         → publish {redacted, author, sessionId}   │
└───────────────────────────┬───────────────────────┘
                            │  authenticated publish (redacted only)
                            ▼
┌─ commons-search (new in-cluster service) ────────┐
│  ingest: re-run FLOOR gate (defense in depth)     │
│          author rate-limit + size cap             │
│  store:  redacted corpus + revocation set         │
│  serve:  GET /api/open-chats/search  (json_engine │
│          shape) — sanitized + injection-stripped  │
└───────────────────────────┬───────────────────────┘
                            │  in-cluster http
                            ▼
┌─ SearXNG ────────────────────────────────────────┐
│  json_engine "noetica commons" → unified results  │
│  (web + open-community-chat in ONE query)         │
└──────────────────────────────────────────────────┘
                            │
                            ▼  (already wired, PR #478)
        Noetica agent web_search → marks EXTERNAL/untrusted
```

`commons-search` is a normal fleet service: `infra/k8s/commons-search/base/{deployment,service,configmap,kustomization}.yaml` + a matrix entry in `images.yml` + an ApplicationSet element in `deploy/argocd/search-services.yaml`, exactly like `searxng`.

---

## 4. Substrate — POLYGLOT store behind one interface (decided)

**Decision (Michael): the commons is polyglot — start with MinIO, socbase, AND hellgraph, all behind a single pluggable `CommonsStore` interface, selected by env.** This mirrors the proven regis `get_backend()` pattern (`hellgraph/ts/src/graph_backend`-style selection): the service depends on the *interface*, never a concrete store, so a deployment picks its backend and the search contract is identical across all three. No store is privileged; the sovereign path (hellgraph) and the pragmatic paths (MinIO, socbase) coexist.

```
interface CommonsStore {
  put(entry: RedactedOpenChat): Promise<void>     // ingest re-runs the floor gate BEFORE this
  revoke(author: string, sessionId: string): Promise<void>
  isRevoked(author: string, sessionId: string): boolean   // live set, checked per query
  search(query: string, limit: number): Promise<OpenChatHit[]>
}
```

Selected by `COMMONS_STORE` env: `minio` | `socbase` | `hellgraph`.

- **`minio`** — redacted entries as objects + an in-service lexical index. Matches the sovereign-registry (zot/MinIO) posture; dependency-light; simplest to stand up.
- **`socbase`** — a Postgres table via the existing socbase/PostgREST plane; queryable SQL, reuses the auth/DB we already run.
- **`hellgraph`** — the **sovereign, append-only, no-central-point** path via the proven `regis-writer.ts` pattern: each instance appends redacted entries to its **own Hypercore log**; **Autobase** merges to a materialized commons view; `commons-search` reads it via the super-peer `/query` (read+govern only — "cannot forge or rewrite"). No node can rewrite or forge another's entries.

**Phasing note:** all three ship behind the interface. MinIO/socbase give community-wide reach immediately and are trivial for the security review to reason about; hellgraph is the end-state sovereign backend. Because they share the `CommonsStore` contract and the external `/api/open-chats/search` shape, moving a deployment from `minio` → `hellgraph` changes an env var, not the API — SearXNG and the review never re-litigate.

---

## 5. Revocation in an append-only world

Publish and revoke are **author-scoped operations**, latest-wins per `(author, sessionId)`:

- `publish` → `{op:'open', author, sessionId, redacted, ts}`
- `revoke`  → `{op:'revoke', author, sessionId, ts}`

The materializer honors the latest op per key. **A revoke may only tombstone entries with a matching `author`** — no node can un-publish another author's chat (nor forge one; Phase 2 gets this from Hypercore's per-log authorship for free, Phase 1 from the author-scoped token).

**Instant-revocation guarantee:** the search service consults a live revocation set on every query, so a revoked chat drops out immediately even before merge/materialization settles — no cached window for another agent. (Matches the #483 local guarantee, extended across the federation.)

---

## 6. Trust, abuse, identity

Open chats are **untrusted input to every other user's agent** — a place someone could deliberately plant an injection or misinformation to reach other people. Layered defenses:

1. **Injection** — `/api/open-chats/search` already runs `sanitizeRetrieved` + `stripPotentialInjection` per snippet (PR #483); the reader's `web_search` re-marks the whole result `EXTERNAL`. Keep both.
2. **Author identity** — pseudonymous via `sovereign-id`; every commons entry carries an author handle for rate-limiting, reputation, and revocation scoping. No real-world identity is required or exposed.
3. **Rate + size limits** — per-author publish rate cap and per-entry size cap at ingest, to bound corpus-poisoning volume.
4. **Reputation / quarantine** — rank/limit by author reputation (digital-soul / sacred-capital); low-reputation entries can be quarantined from cross-user search until vouched. (Phase 2+.)
5. **Moderation / report** — a report path that appends a moderator tombstone (author-independent, privileged). Abuse takedown without breaking append-only.
6. **NER upgrade (opt-in)** — entitled instances run `regis-entity-graph` NER→policy-veto locally before publish for named-entity PII (person names, org+role prose) the regex floor misses. Never a hard dependency; the floor always runs regardless.

---

## 7. The SearXNG engine (drops in once Phase 1 is deployed)

Add to `infra/k8s/searxng/base/configmap.yaml` `settings.yml` under `engines:` — **no custom Python image** needed, the declarative `json_engine` covers it:

```yaml
- name: noetica commons
  engine: json_engine
  search_url: http://commons-search.socioprophet.svc.cluster.local:8080/api/open-chats/search?q={query}
  results_query: results
  url_query: url
  title_query: title
  content_query: content
  categories: [general]
  shortcut: nc
  timeout: 4.0
```

One SearXNG query then returns web results + open-community-chat matches, unified — which is the whole point.

---

## 8. Phasing / task breakdown

| Phase | Deliverable | State |
|---|---|---|
| 0 | Per-instance gate + redacted index + endpoints + toggle | ✅ Noetica PR #483 (review-gated) |
| 1a | `commons-search` service (Dockerfile → images.yml → ArgoCD), MinIO/socbase store, floor-gate on ingest, `/api/open-chats/search` | ⏳ this spec |
| 1b | Authenticated publish channel from Noetica → commons-search (author-scoped) | ⏳ |
| 1c | SearXNG `json_engine` wired (§7) + security review of the exposure path | ⏳ |
| 2 | Swap store for hellgraph-federated Autobase log (regis-writer pattern); contract unchanged | later |
| 2+ | Reputation/quarantine + moderation takedown | later |

---

## 9. Decisions (resolved 2026-07-16)

1. **Store** — ✅ **Polyglot: `CommonsStore` interface with `minio` + `socbase` + `hellgraph` backends, env-selected** (§4). Start with all three behind the interface; no store privileged.
2. **Publish auth** — ✅ **sovereign-id pseudonym** per instance. It's the author identity revocation-scoping and reputation need anyway.
3. **Search reach (Phase 1)** — ✅ **Global + rate-limited + sanitized.** Any agent finds an open chat immediately; reputation-gating is added in Phase 2 once there's signal to gate on.

## 10. First buildable unit (Phase 1a)

`commons-search` service skeleton: the `CommonsStore` interface + the three backends (env-selected), the floor-gate-on-ingest, `POST /publish` (sovereign-id authed), `DELETE`/revoke (author-scoped) + live revocation set, `GET /api/open-chats/search` (json_engine shape, sanitized), per-author rate/size caps. Deployed like the fleet (Dockerfile → images.yml → ArgoCD `search-services.yaml`). Then §7 wires SearXNG and a security review runs on the exposure path before it goes live.
