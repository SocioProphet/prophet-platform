// health-twin — the Digital Health Twin engine (walking skeleton). Serves the person's records as a
// FHIR-lite bundle keyed to organ systems (so the anatomical diagram is the index), plus GOVERNED
// consent grants: a designated agent gets a scoped, time-boxed, receipted, revocable read grant, and
// every access is a receipt. In production this runs LOCAL-FIRST on the person's own node — never a
// shared cloud. Here it holds one clearly-synthetic subject. Node http, binds 0.0.0.0.
//
// NOT a medical device. NOT diagnostic. Organises + retrieves + governs sharing of a person's own
// records. Synthetic data only in this skeleton — no real PHI.
import http from 'node:http';
import { SUBJECT, SYSTEMS, OBSERVATIONS, CONDITIONS, ENCOUNTERS, IMAGING, type Grant } from './data.js';

const PORT = Number(process.env.PORT ?? 8097);

function djb2(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) & 0xffffffff;
  return (h >>> 0).toString(16).padStart(8, '0');
}
function receipt(kind: string, parts: string[]): { id: string; verifier: 'health-twin'; at: string } {
  return { id: `ht-${kind}-${djb2(parts.join('|'))}`, verifier: 'health-twin', at: new Date().toISOString() };
}

// In-memory grant ledger (skeleton). Local-first store in production.
const grants: Grant[] = [];

function bundle() {
  // group records per system for the anatomical index
  const bySystem = SYSTEMS.map((s) => ({
    ...s,
    observations: OBSERVATIONS.filter((o) => o.system === s.id),
    conditions: CONDITIONS.filter((c) => c.system === s.id),
    encounters: ENCOUNTERS.filter((e) => e.system === s.id),
    imaging: IMAGING.filter((i) => i.system === s.id),
  }));
  return {
    subject: SUBJECT,
    systems: bySystem,
    timeline: [...ENCOUNTERS].sort((a, b) => (a.date < b.date ? 1 : -1)),
    counts: { observations: OBSERVATIONS.length, conditions: CONDITIONS.length, encounters: ENCOUNTERS.length, imaging: IMAGING.length },
    grants: grants.map((g) => ({ ...g, active: !g.revoked && new Date(g.expires_at) > new Date() })),
    disclaimer: 'Synthetic sample. Not a real person, not medical advice. This tool organises records; it does not diagnose.',
  };
}

function send(res: http.ServerResponse, code: number, body: unknown) {
  res.writeHead(code, { 'content-type': 'application/json', 'access-control-allow-origin': '*', 'access-control-allow-headers': 'content-type', 'access-control-allow-methods': 'POST, GET, OPTIONS' });
  res.end(JSON.stringify(body));
}
function readJson(req: http.IncomingMessage): Promise<any> {
  return new Promise((resolve, reject) => {
    let raw = ''; req.on('data', (c) => { raw += c; if (raw.length > 2_000_000) req.destroy(); });
    req.on('end', () => { try { resolve(raw ? JSON.parse(raw) : {}); } catch (e) { reject(e); } });
    req.on('error', reject);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url ?? '/', `http://${req.headers.host}`);
  if (req.method === 'OPTIONS') return send(res, 204, {});
  if (req.method === 'GET' && url.pathname === '/healthz') return send(res, 200, { ok: true, service: 'health-twin' });

  // The twin bundle (the surface's one read).
  if (req.method === 'GET' && url.pathname === '/api/health/twin') return send(res, 200, bundle());

  // Grant a designated agent a scoped, time-boxed read grant — receipted.
  if (req.method === 'POST' && url.pathname === '/api/health/grant') {
    try {
      const b = await readJson(req);
      const agent = String(b.agent ?? '').trim();
      const scope = String(b.scope ?? 'all systems').trim() || 'all systems';
      const ttlDays = Math.max(1, Math.min(365, Number(b.ttlDays ?? 30)));
      if (!agent) return send(res, 422, { error: 'agent required' });
      const now = new Date();
      const g: Grant = {
        id: `grant-${djb2([agent, scope, String(now.getTime())].join('|'))}`,
        agent, scope, granted_at: now.toISOString(),
        expires_at: new Date(now.getTime() + ttlDays * 86400000).toISOString(),
        revoked: false, reads: 0, receipt: receipt('grant', [agent, scope, String(ttlDays)]).id,
      };
      grants.unshift(g);
      return send(res, 200, { grant: g });
    } catch { return send(res, 400, { error: 'bad json' }); }
  }

  // Revoke a grant — read-enforced: future reads by that agent are blocked.
  if (req.method === 'POST' && url.pathname === '/api/health/revoke') {
    try {
      const b = await readJson(req);
      const g = grants.find((x) => x.id === String(b.grant));
      if (!g) return send(res, 404, { error: 'grant not found' });
      g.revoked = true;
      return send(res, 200, { grant: g, receipt: receipt('revoke', [g.id]) });
    } catch { return send(res, 400, { error: 'bad json' }); }
  }

  // An agent exercises a grant to read a slice — the access itself is a receipt (or a block).
  if (req.method === 'POST' && url.pathname === '/api/health/agent-read') {
    try {
      const b = await readJson(req);
      const g = grants.find((x) => x.id === String(b.grant));
      if (!g) return send(res, 404, { error: 'grant not found' });
      if (g.revoked) return send(res, 403, { blocked: true, reason: 'grant revoked — read denied' });
      if (new Date(g.expires_at) <= new Date()) return send(res, 403, { blocked: true, reason: 'grant expired — read denied' });
      g.reads += 1;
      return send(res, 200, { agent: g.agent, scope: g.scope, reads: g.reads, receipt: receipt('read', [g.id, String(g.reads)]) });
    } catch { return send(res, 400, { error: 'bad json' }); }
  }

  send(res, 404, { error: 'not found' });
});

server.listen(PORT, () => { console.log(`health-twin listening on :${PORT}`); });
