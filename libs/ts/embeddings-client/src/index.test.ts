import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  embed,
  embedOne,
  embeddingRequest,
  EmbeddingSpaceError,
  EMBEDDINGS_MODEL,
  EMBEDDINGS_DIMENSION,
} from './index.ts';

// A fake sovereign service. `over` lets each test bend one thing.
function fakeFetch(over: { model?: string; dim?: number; status?: number; count?: number } = {}): typeof fetch {
  const model = over.model ?? EMBEDDINGS_MODEL;
  const dim = over.dim ?? EMBEDDINGS_DIMENSION;
  return (async (_url: string, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body ?? '{}'));
    const inputs: string[] = Array.isArray(body.input) ? body.input : [body.input];
    const n = over.count ?? inputs.length;
    const data = Array.from({ length: n }, (_v, index) => ({
      object: 'embedding',
      index,
      embedding: Array.from({ length: dim }, (_x, i) => Math.sin(index + i)),
    }));
    return {
      ok: (over.status ?? 200) < 400,
      status: over.status ?? 200,
      json: async () => ({ object: 'list', model, data }),
    } as unknown as Response;
  }) as unknown as typeof fetch;
}

test('happy path: returns one pinned-dimension vector per input, in order', async () => {
  const vecs = await embed(['alpha', 'beta'], { fetchImpl: fakeFetch() });
  assert.equal(vecs.length, 2);
  assert.equal(vecs[0].length, EMBEDDINGS_DIMENSION);
  assert.equal(vecs[1].length, EMBEDDINGS_DIMENSION);
});

test('request is contract-shaped: sends the pinned model id', async () => {
  let sent: any;
  const capturing = (async (_u: string, init?: RequestInit) => {
    sent = JSON.parse(String(init?.body));
    return { ok: true, status: 200, json: async () => ({ model: EMBEDDINGS_MODEL, data: [{ index: 0, embedding: Array(EMBEDDINGS_DIMENSION).fill(0) }] }) } as unknown as Response;
  }) as unknown as typeof fetch;
  await embedOne('x', { fetchImpl: capturing });
  assert.equal(sent.model, EMBEDDINGS_MODEL);
  assert.deepEqual(sent.input, ['x']);
});

// ── TEETH: drift must be a refusal, not a silent wrong ──────────────────────
test('fail-closed: wrong dimension throws EmbeddingSpaceError', async () => {
  await assert.rejects(
    () => embed('x', { fetchImpl: fakeFetch({ dim: 512 }) }),
    (e: unknown) => e instanceof EmbeddingSpaceError && /length 512/.test((e as Error).message),
  );
});

test('fail-closed: wrong model throws EmbeddingSpaceError', async () => {
  await assert.rejects(
    () => embed('x', { fetchImpl: fakeFetch({ model: 'ollama/nomic-embed-text' }) }),
    (e: unknown) => e instanceof EmbeddingSpaceError && /incomparable space/.test((e as Error).message),
  );
});

test('fail-closed: vector-count mismatch throws', async () => {
  await assert.rejects(
    () => embed(['a', 'b', 'c'], { fetchImpl: fakeFetch({ count: 2 }) }),
    (e: unknown) => e instanceof EmbeddingSpaceError,
  );
});

test('fail-closed: HTTP error throws', async () => {
  await assert.rejects(
    () => embed('x', { fetchImpl: fakeFetch({ status: 503 }) }),
    (e: unknown) => e instanceof EmbeddingSpaceError && /HTTP 503/.test((e as Error).message),
  );
});

test('empty input short-circuits to no vectors (no network call)', async () => {
  const boom = (() => { throw new Error('must not fetch'); }) as unknown as typeof fetch;
  assert.deepEqual(await embed([], { fetchImpl: boom }), []);
});

test('embeddingRequest builds the pinned contract record', () => {
  assert.deepEqual(embeddingRequest('x'), {
    model: EMBEDDINGS_MODEL,
    dimension: EMBEDDINGS_DIMENSION,
    input: 'x',
  });
});
