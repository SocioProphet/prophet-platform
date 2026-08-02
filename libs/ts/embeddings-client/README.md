# @socioprophet/embeddings-client

The **one** client for the estate's sovereign embedding service
(`prophet-platform/apps/embeddings`, serving `nomic-ai/nomic-embed-text-v1.5`
over an OpenAI-compatible `POST /v1/embeddings`).

It is the **runtime** half of the ingestion-pipeline seam. The
[`sourceos-spec` `EmbeddingRequest` contract](../../../../sourceos-spec/specs/ingestion-pipeline-contract.md)
pins the model and dimension *statically* (by `const`); this client enforces the
**same pin at call time and fails closed** on any drift.

## Why it exists

`health-twin`, `hellgraph-service`, and Noetica's `doc-store` each grew their own
`/v1/embeddings` fetch — with different default model strings
(`nomic-embed-text` vs `nomic-ai/nomic-embed-text-v1.5`), different URLs, and
**no verification of the response**. That is the `platform-services`-not-`Noetica`-only
duplication, and a live vector-space-drift risk: two producers writing vectors
that silently are not comparable. This lib is the single reuse point.

## Use

```ts
import { embed, embedOne } from '@socioprophet/embeddings-client';

const vectors = await embed(['first chunk', 'second chunk']); // number[][], each length 768
const one = await embedOne('a query');                         // number[]
```

Point it at the service with `EMBEDDINGS_URL` (default
`http://embeddings:8080/v1/embeddings`) or the `url` option.

## The guarantee (fail closed)

`embed()` returns **only** vectors provably in the pinned space. It throws
`EmbeddingSpaceError` — a refusal, never a fallback — when:

- the response `model` is not `nomic-ai/nomic-embed-text-v1.5` (a different space);
- any vector length is not `768` (a truncated/foreign vector);
- the vector count does not match the input count, or the service errors.

A caller gets correct vectors or an error — never a silently-incomparable one.

## Test

```
node --import tsx --test src/*.test.ts
```

Includes teeth tests: wrong dimension, wrong model, count mismatch and HTTP
error each raise `EmbeddingSpaceError`.

## Adoption (rollout)

Replace the hand-rolled `/v1/embeddings` fetches in `apps/hellgraph-service`
(`graphrag.ts` — currently defaults to the unpinned `nomic-embed-text` and does
no dimension check), `apps/health-twin` (`reconcile/clients.ts`), and — via the
Noetica `doc-store` rewire (PR-3) — the Noetica producer, so all embedding lands
in one verified space.
