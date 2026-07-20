// portfolio-agent — the sovereign CLOUD portfolio agent (Portfolio ②) over HTTP, so the same
// proof-carrying tool layer the cockpit runs in-browser (①) can run server-side / autonomously.
// The cockpit's cloud path calls this on :8094; every response carries a deterministic receipt.
import * as http from 'node:http';
import { runPortfolioAgent, type Position } from './agent.js';

const PORT = Number(process.env.PORT ?? 8094);

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
  if (url.pathname === '/healthz') {
    return json(res, 200, { ok: true, service: 'portfolio-agent', capabilities: ['analyze'] });
  }
  // POST /analyze { positions:[{symbol,name,qty,avgCost,last,series?}], goal?, equity? }
  if (req.method === 'POST' && url.pathname === '/analyze') {
    try {
      const body = JSON.parse((await readBody(req)) || '{}') as { positions?: Position[]; goal?: string; equity?: number };
      const book = (body.positions ?? []).filter((p) => p && p.qty > 0);
      const equity = typeof body.equity === 'number' ? body.equity : book.reduce((s, p) => s + p.last * p.qty, 0);
      const result = runPortfolioAgent(body.goal ?? 'Assess concentration and downside risk', book, equity);
      return json(res, 200, result);
    } catch (e) {
      return json(res, 400, { error: 'bad request', detail: e instanceof Error ? e.message : String(e) });
    }
  }
  return json(res, 404, { error: 'not_found' });
}).listen(PORT, () => {
  // http.listen(PORT) binds 0.0.0.0 by default — no localhost-bind CrashLoop trap.
  // eslint-disable-next-line no-console
  console.log(`portfolio-agent serving on :${PORT}`);
});
