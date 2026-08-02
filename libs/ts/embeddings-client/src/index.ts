// @socioprophet/embeddings-client — the one client for the estate's sovereign
// embedding service (prophet-platform apps/embeddings). It is the runtime
// complement to the sourceos-spec Ingestion-Pipeline contract's EmbeddingRequest:
// the contract pins the model and dimension by `const` statically; this client
// enforces the SAME pin at call time and FAILS CLOSED on any drift, so a caller
// can never silently land vectors from a different, incomparable space.
//
// Why this exists: health-twin, hellgraph-service and Noetica's doc-store each
// grew their own /v1/embeddings fetch, with different default model strings
// (e.g. 'nomic-embed-text' vs 'nomic-ai/nomic-embed-text-v1.5') and NO response
// verification — the platform-services-not-Noetica-only duplication, and a live
// vector-space-drift risk. This lib is the single reuse point for all of them.

/** The sovereign embedding model. Pinned — matches sourceos-spec EmbeddingRequest.model. */
export const EMBEDDINGS_MODEL = 'nomic-ai/nomic-embed-text-v1.5';
/** The pinned embedding dimension. Matches sourceos-spec EmbeddingRequest.dimension. */
export const EMBEDDINGS_DIMENSION = 768;

/** The contract-shaped request record (mirror of sourceos-spec EmbeddingRequest). */
export interface EmbeddingRequest {
  readonly model: typeof EMBEDDINGS_MODEL;
  readonly dimension: typeof EMBEDDINGS_DIMENSION;
  readonly input: string | readonly string[];
}

export interface EmbedOptions {
  /** Full URL of the sovereign service's embeddings endpoint (…/v1/embeddings). */
  url?: string;
  /** Optional bearer token. */
  apiKey?: string;
  /** Injected for tests; defaults to global fetch. */
  fetchImpl?: typeof fetch;
  /** Per-call timeout (ms). */
  timeoutMs?: number;
}

/** Thrown when the service returns vectors that are not in the pinned space.
 *  This is a REFUSAL, not a fallback — the whole point is that drift is loud. */
export class EmbeddingSpaceError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'EmbeddingSpaceError';
  }
}

const DEFAULT_URL =
  (typeof process !== 'undefined' && process.env && process.env['EMBEDDINGS_URL']?.trim()) ||
  'http://embeddings:8080/v1/embeddings';

interface OpenAIEmbeddingsResponse {
  object?: string;
  model?: string;
  data?: Array<{ object?: string; index?: number; embedding?: number[] }>;
}

/**
 * Embed one or more texts against the sovereign service and RETURN ONLY vectors
 * that are provably in the pinned space. Any response whose model differs from
 * {@link EMBEDDINGS_MODEL}, or any vector whose length differs from
 * {@link EMBEDDINGS_DIMENSION}, throws {@link EmbeddingSpaceError} — the caller
 * gets correct vectors or an error, never a silently-incomparable vector.
 *
 * Returns one vector per input string, in input order.
 */
export async function embed(
  input: string | readonly string[],
  opts: EmbedOptions = {},
): Promise<number[][]> {
  const texts = typeof input === 'string' ? [input] : [...input];
  if (texts.length === 0) return [];

  const url = opts.url ?? DEFAULT_URL;
  const fetchImpl = opts.fetchImpl ?? fetch;
  const headers: Record<string, string> = { 'content-type': 'application/json' };
  if (opts.apiKey) headers['authorization'] = `Bearer ${opts.apiKey}`;

  // Wire body is OpenAI/Ollama compatible; we always send the pinned model id so
  // Wire body is OpenAI/Ollama compatible ({model, input}); the full contract
  // record (incl. dimension) is available via embeddingRequest().
  const body = JSON.stringify({ model: EMBEDDINGS_MODEL, input: texts });

  // Fail closed on transport too: fetch/JSON failures must surface as
  // EmbeddingSpaceError so a caller gets correct vectors or that error — never
  // some other exception type that slips past the contract.
  let res: Response;
  try {
    res = await fetchImpl(url, {
      method: 'POST',
      headers,
      body,
      signal: AbortSignal.timeout(opts.timeoutMs ?? 15_000),
    });
  } catch (err) {
    throw new EmbeddingSpaceError(`embeddings request to ${url} failed: ${(err as Error).message}`);
  }
  if (!res.ok) {
    throw new EmbeddingSpaceError(`embeddings service returned HTTP ${res.status} from ${url}`);
  }

  let payload: OpenAIEmbeddingsResponse;
  try {
    payload = (await res.json()) as OpenAIEmbeddingsResponse;
  } catch (err) {
    throw new EmbeddingSpaceError(`embeddings service returned unparseable JSON from ${url}: ${(err as Error).message}`);
  }

  // Fail closed on model drift — INCLUDING a missing model. The guarantee is
  // "provably in the pinned space"; an unnamed model is unverifiable, so refuse.
  if (payload.model !== EMBEDDINGS_MODEL) {
    throw new EmbeddingSpaceError(
      `embeddings service reported model ${JSON.stringify(payload.model ?? null)}, not the pinned ` +
        `${JSON.stringify(EMBEDDINGS_MODEL)} — an unverifiable or different space`,
    );
  }

  const rows = payload.data;
  if (!Array.isArray(rows) || rows.length !== texts.length) {
    throw new EmbeddingSpaceError(
      `embeddings service returned ${rows?.length ?? 0} vectors for ${texts.length} inputs`,
    );
  }

  // Trust `index` only after proving it is a permutation of 0..n-1. Duplicate or
  // missing indices with a correct count would otherwise silently associate a
  // vector with the wrong input — the exact silent-wrong the guarantee forbids.
  const n = rows.length;
  const seen = new Array<boolean>(n).fill(false);
  for (const row of rows) {
    const idx = row.index;
    if (typeof idx !== 'number' || !Number.isInteger(idx) || idx < 0 || idx >= n || seen[idx]) {
      throw new EmbeddingSpaceError(
        `embeddings response indices are not a permutation of 0..${n - 1} ` +
          `(bad or duplicate index ${JSON.stringify(idx)})`,
      );
    }
    seen[idx] = true;
  }

  const ordered = [...rows].sort((a, b) => (a.index as number) - (b.index as number));
  return ordered.map((row, i) => {
    const vec = row.embedding;
    if (!Array.isArray(vec) || vec.length !== EMBEDDINGS_DIMENSION) {
      throw new EmbeddingSpaceError(
        `vector ${i} has length ${vec?.length ?? 0}, not the pinned ${EMBEDDINGS_DIMENSION} — ` +
          `a truncated or foreign vector is not in the shared space`,
      );
    }
    return vec;
  });
}

/** Convenience for the common single-text case. */
export async function embedOne(text: string, opts: EmbedOptions = {}): Promise<number[]> {
  const [vec] = await embed(text, opts);
  return vec;
}

/** Build the contract-shaped request record (for provenance / typing at call sites). */
export function embeddingRequest(input: string | readonly string[]): EmbeddingRequest {
  return { model: EMBEDDINGS_MODEL, dimension: EMBEDDINGS_DIMENSION, input };
}
