# hellgraph-service

A small Node/TS microservice that exposes the shared **HellGraph AtomSpace engine**
(`@socioprophet/hellgraph`) over HTTP. prophet-platform's other services (Go,
Python, the Vue browser app) can use the metagraph — PLN, ECAN, pattern matching,
SHACL — without embedding a TypeScript engine, since the engine is Node-only.

## Run
```bash
npm install
npm start          # tsx src/server.ts (PORT=8090)
npm run typecheck
```

## API
| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | liveness + engine export count |
| GET | `/api/graph/stats` | node / edge counts |
| GET | `/api/graph/log?since=&limit=` | log-tail for materializers: creation events after `since` (seq asc, ≤1000) + `cursor` + `version` |
| POST | `/api/graph/node` | `{ id, labels[], properties? }` → upsert node |
| POST | `/api/graph/edge` | `{ label, from, to, properties? }` → add edge |
| GET | `/api/graph/query?label=X` | nodes carrying a label |
| POST | `/api/graph/reason` | run PLN forward-chaining |
| POST | `/api/membrane/decide` | spec-valid `EffectRequest` wrapping an `OrderIntent` → policy kernel v0 → `EffectDecision` node (idempotent by `idempotencyKey`), sealed via compute-gateway |

## Wave 2 doors (flag-gated governance)
- **AUTH_ENFORCE** (default `off`): `on` requires HMAC bearer tokens on `/api/graph/*` +
  `/api/membrane/*` — scopes `graph:read` / `graph:write` / `graph:enrich` (`src/auth.ts`;
  mint with `mintGraphToken`). `on` without `AUTH_HMAC_SECRET` refuses startup (fail-closed).
- **MEMBRANE_ENFORCE** (default `off`): `on` = the B-after-A gate — a node write labeled
  `ExecutionReport` requires `properties.decisionRef` → an existing **approved**
  `EffectDecision` with matching `intentRef`, else a typed 403; `EffectDecision` nodes mint
  only via `POST /api/membrane/decide` (`src/membrane.ts`; vendored sha-asserted
  sourceos-spec schemas in `src/contract.ts` + `src/schemas/`).

## Why a service (not a library import)
The engine uses Node built-ins (`node:crypto`, `fs`) and cannot run in the browser
Vue app. Exposing it as an HTTP service lets every language in the platform consume
it over the network. The dependency is pinned to a tagged release
(`@socioprophet/hellgraph#v0.2.0`).
