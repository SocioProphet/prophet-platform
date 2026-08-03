const { canonicalize, hmacSha256Hex, stableHash } = require('./canonical');
const { NonceStore } = require('./nonce-store');

const DEFAULT_TTL_SECONDS = 900;

function issueLocalGrant(payload, key, now = Math.floor(Date.now() / 1000)) {
  const ttl = payload.ttl_seconds || DEFAULT_TTL_SECONDS;
  if (ttl !== DEFAULT_TTL_SECONDS) throw new Error('ttl must be 900 seconds');

  const body = {
    token_id: payload.token_id,
    session_id: payload.session_id,
    agent_id: payload.agent_id,
    issuer_node: payload.issuer_node,
    aud: 'gitea-sovereign',
    issued_at: now,
    not_before: now,
    expires_at: now + ttl,
    scope: payload.scope,
    intent_hash: payload.intent_hash,
    policy_decision_ref: payload.policy_decision_ref,
    grant_ref: payload.grant_ref,
    device_hash: payload.device_hash,
    replay_nonce: payload.replay_nonce,
    cross_node: payload.cross_node === true,
    key_id: payload.key_id || 'local-hmac-v1',
    alg: 'HS256'
  };
  const signature = hmacSha256Hex(key, canonicalize(body));
  return { ...body, signature };
}

function verifyLocalGrant(grant, key, nonceStore, now = Math.floor(Date.now() / 1000)) {
  if (!grant || typeof grant !== 'object') return { ok: false, reason: 'grant.invalid' };
  if (grant.aud !== 'gitea-sovereign') return { ok: false, reason: 'grant.audience' };
  if (grant.alg !== 'HS256') return { ok: false, reason: 'grant.algorithm' };
  if (grant.not_before > now) return { ok: false, reason: 'grant.not_before' };
  if (grant.expires_at <= now) return { ok: false, reason: 'grant.expired' };
  if (grant.expires_at - grant.issued_at !== DEFAULT_TTL_SECONDS) return { ok: false, reason: 'grant.ttl' };

  const { signature, ...body } = grant;
  const expected = hmacSha256Hex(key, canonicalize(body));
  if (signature !== expected) return { ok: false, reason: 'grant.signature' };

  const store = nonceStore || new NonceStore();
  const nonce = store.consume(grant.replay_nonce, now);
  if (!nonce.ok) return { ok: false, reason: nonce.reason };

  return { ok: true, reason: 'grant.verified', body_hash: stableHash(body) };
}

function revokeLocalGrant(grant, reason = 'revoked') {
  if (!grant || typeof grant !== 'object') return { ok: false, reason: 'grant.invalid' };
  return {
    ok: true,
    event_type: 'token.revoke',
    token_id: grant.token_id,
    session_id: grant.session_id,
    agent_id: grant.agent_id,
    reason
  };
}

module.exports = {
  DEFAULT_TTL_SECONDS,
  issueLocalGrant,
  revokeLocalGrant,
  verifyLocalGrant
};
