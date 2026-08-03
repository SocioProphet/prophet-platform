#!/usr/bin/env node
// authority-server — the sovereign token authority as a live HTTP service (L1).
//
// Wraps core/local-authority.js (issueLocalGrant/verifyLocalGrant) behind a
// zero-dependency node:http server so the agentic shell can request short-lived
// (900s) ScopedAgentTokens for Gitea ops without ever seeing the HMAC root.
// The root is read once from $GITEA_SIGNING_KEY (the minted k8s Secret) and never
// leaves this process. The runner/shell calls /v1/tokens/issue; the signing key
// stays in the cluster.
//
//   GET  /healthz              -> 200 {ok:true}
//   POST /v1/tokens/issue      -> mint a ScopedAgentToken (body = grant payload)
//   POST /v1/tokens/verify     -> {ok, reason} for a presented token
'use strict';
const http = require('node:http');
const crypto = require('node:crypto');
const { issueLocalGrant, verifyLocalGrant } = require('../core/local-authority');
const { NonceStore } = require('../core/nonce-store');

const KEY = process.env.GITEA_SIGNING_KEY;
const PORT = Number(process.env.PORT || 8081);
const ISSUER = process.env.ISSUER_NODE || 'org-primary';
const nonces = new NonceStore();

function readJson(req) {
  return new Promise((resolve, reject) => {
    let d = '';
    req.on('data', (c) => { d += c; if (d.length > 1 << 20) reject(new Error('body too large')); });
    req.on('end', () => { try { resolve(d ? JSON.parse(d) : {}); } catch (e) { reject(e); } });
  });
}
function send(res, code, obj) { const b = JSON.stringify(obj); res.writeHead(code, { 'content-type': 'application/json' }); res.end(b); }

function issue(payload) {
  // fill server-authoritative fields; the caller supplies scope/intent/policy refs
  const sha = (s) => crypto.createHash('sha256').update(String(s)).digest('hex');
  const full = {
    token_id: payload.token_id || crypto.randomUUID(),
    session_id: payload.session_id || crypto.randomUUID(),
    agent_id: payload.agent_id || crypto.randomUUID(),
    issuer_node: ISSUER,
    scope: payload.scope || { repos: [], branches: [], ops: ['read'], paths_allow: [], paths_deny: [] },
    intent_hash: payload.intent_hash || sha('agentic-shell'),
    policy_decision_ref: payload.policy_decision_ref || 'policy-fabric://decisions/source-control/agentic-shell',
    grant_ref: payload.grant_ref || 'mcp-a2a://grants/source-control/agentic-shell',
    device_hash: payload.device_hash || sha(payload.device_seed || 'shell'),
    replay_nonce: payload.replay_nonce || ('nonce-' + crypto.randomBytes(8).toString('hex')),
    cross_node: payload.cross_node === true,
  };
  return issueLocalGrant(full, KEY);
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === 'GET' && req.url === '/healthz') {
      return send(res, 200, { ok: true, service: 'gitea-sovereign-authority', key_loaded: Boolean(KEY) });
    }
    if (!KEY) return send(res, 503, { ok: false, reason: 'GITEA_SIGNING_KEY not mounted (authority cannot sign)' });
    if (req.method === 'POST' && req.url === '/v1/tokens/issue') {
      const token = issue(await readJson(req));
      return send(res, 200, token);
    }
    if (req.method === 'POST' && req.url === '/v1/tokens/verify') {
      const { grant } = await readJson(req);
      return send(res, 200, verifyLocalGrant(grant, KEY, nonces));
    }
    return send(res, 404, { ok: false, reason: 'not found' });
  } catch (e) {
    return send(res, 400, { ok: false, reason: String(e.message || e) });
  }
});

module.exports = { server, issue };

if (require.main === module) {
  server.listen(PORT, () => console.log(`gitea-sovereign authority on :${PORT} (key_loaded=${Boolean(KEY)})`));
}
