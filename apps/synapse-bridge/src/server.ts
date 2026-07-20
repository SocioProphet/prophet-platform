// synapse-bridge — SynapseIQ's language-intelligence functions over HTTP so the cockpit's NLP/IE
// surface can use them: text normalization + KKO (Peircean) type classification. Vendored from
// synapseiq/bridge/server.ts. The cockpit's ieApi.kkoClassify → /svc/synapse → this on :8092.
import * as http from 'node:http';
import { normalizeName, normalizeToken, kkoClassOf } from './enrichment.js';

const PORT = Number(process.env.PORT ?? 8092);

function json(res: http.ServerResponse, code: number, body: unknown): void {
  res.writeHead(code, {
    'content-type': 'application/json',
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET, POST, OPTIONS',
    'access-control-allow-headers': 'content-type',
  });
  res.end(JSON.stringify(body));
}
function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve) => { let d = ''; req.on('data', (c) => (d += c)); req.on('end', () => resolve(d)); });
}

http.createServer(async (req, res) => {
  const url = new URL(req.url ?? '/', `http://localhost:${PORT}`);
  if (req.method === 'OPTIONS') return json(res, 204, {});
  if (url.pathname === '/healthz') return json(res, 200, { ok: true, service: 'synapseiq-bridge', capabilities: ['normalize', 'kko-class'] });
  if (req.method === 'POST' && url.pathname === '/normalize') {
    const { names } = JSON.parse((await readBody(req)) || '{}') as { names?: string[] };
    return json(res, 200, { results: (names ?? []).map((n) => ({ input: n, name: normalizeName(n), token: normalizeToken(n) })) });
  }
  if (req.method === 'POST' && url.pathname === '/kko-class') {
    const { types } = JSON.parse((await readBody(req)) || '{}') as { types?: string[] };
    return json(res, 200, { engine: 'synapseiq/enrichment', results: (types ?? []).map((t) => ({ type: t, kko: kkoClassOf(t) })) });
  }
  json(res, 404, { error: 'not found' });
}).listen(PORT, () => console.log(`synapseiq-bridge on :${PORT}`));
