// academy-board — the sovereign scoring service behind the Academy mastery check.
// The cockpit posts a pick (or a whole board); the answer key lives here, and every verdict
// comes back with a deterministic receipt. Node http, no framework, binds 0.0.0.0 so the
// kubelet liveness probe reaches it (a 127.0.0.1 bind → CrashLoop 137).

import http from 'node:http';
import { gradeItem, gradeBoard, courseKnown } from './board.js';

const PORT = Number(process.env.PORT ?? 8095);

function send(res: http.ServerResponse, code: number, body: unknown) {
  const s = JSON.stringify(body);
  res.writeHead(code, {
    'content-type': 'application/json',
    'access-control-allow-origin': '*',
    'access-control-allow-headers': 'content-type',
    'access-control-allow-methods': 'POST, GET, OPTIONS',
  });
  res.end(s);
}

function readJson(req: http.IncomingMessage): Promise<any> {
  return new Promise((resolve, reject) => {
    let raw = '';
    req.on('data', (c) => { raw += c; if (raw.length > 1_000_000) req.destroy(); });
    req.on('end', () => { try { resolve(raw ? JSON.parse(raw) : {}); } catch (e) { reject(e); } });
    req.on('error', reject);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url ?? '/', `http://${req.headers.host}`);
  if (req.method === 'OPTIONS') return send(res, 204, {});

  if (req.method === 'GET' && url.pathname === '/healthz') return send(res, 200, { ok: true, service: 'academy-board' });

  if (req.method === 'POST' && url.pathname === '/grade') {
    try {
      const b = await readJson(req);
      const courseId = String(b.courseId ?? '');
      const itemId = String(b.itemId ?? '');
      const pick = Number(b.pick);
      if (!courseKnown(courseId)) return send(res, 404, { error: `unknown course ${courseId}` });
      if (!Number.isInteger(pick)) return send(res, 400, { error: 'pick must be an integer index' });
      const v = gradeItem(courseId, itemId, pick);
      if (!v) return send(res, 404, { error: `unknown item ${itemId}` });
      return send(res, 200, v);
    } catch { return send(res, 400, { error: 'bad json' }); }
  }

  if (req.method === 'POST' && url.pathname === '/grade-board') {
    try {
      const b = await readJson(req);
      const courseId = String(b.courseId ?? '');
      const subs = Array.isArray(b.submissions) ? b.submissions : [];
      const v = gradeBoard(courseId, subs.map((s: any) => ({ itemId: String(s.itemId), pick: Number(s.pick) })));
      if (!v) return send(res, 404, { error: `unknown course ${courseId}` });
      return send(res, 200, v);
    } catch { return send(res, 400, { error: 'bad json' }); }
  }

  send(res, 404, { error: 'not found' });
});

server.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`academy-board listening on :${PORT}`);
});
