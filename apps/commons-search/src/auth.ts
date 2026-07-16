/**
 * auth.ts — who may publish, and as whom.
 *
 * Phase 1a: publishing requires a coarse instance token (COMMONS_PUBLISH_TOKEN) — only trusted Noetica instances
 * can write to the commons at all — and carries the author's sovereign-id pseudonym in `X-Sovereign-Id`, which
 * scopes revocation and (later) reputation. The pseudonym is trusted transitively through the instance token here;
 * binding it cryptographically (a per-author signature the aggregator verifies, so a compromised instance can't
 * publish AS another user) is the documented hardening step and slots in behind this same function.
 *
 * Search + revoke-by-owner are separate: search is public (the whole point of a commons); revoke is author-scoped
 * by the pseudonym on the token, so no caller can revoke another author's chat.
 */
import type { IncomingMessage } from 'node:http'

export interface Principal { author: string }

export interface AuthResult { ok: boolean; principal?: Principal; error?: string }

/** Bounded pseudonym: printable, no whitespace, capped — keeps it a safe map key + storage value. */
function cleanPseudonym(v: string): string {
  return v.replace(/[^\w.:@-]/g, '').slice(0, 128)
}

export function authenticatePublish(req: IncomingMessage): AuthResult {
  const need = process.env['COMMONS_PUBLISH_TOKEN'] ?? ''
  // Fail closed: if no publish token is configured, refuse ALL publishes rather than accept anonymous writes.
  if (!need) return { ok: false, error: 'commons publishing is not configured (COMMONS_PUBLISH_TOKEN unset)' }
  const auth = req.headers['authorization']
  const got = (Array.isArray(auth) ? auth[0] : auth ?? '').replace(/^Bearer\s+/i, '')
  if (got !== need) return { ok: false, error: 'invalid or missing publish token' }
  const sid = req.headers['x-sovereign-id']
  const author = cleanPseudonym(Array.isArray(sid) ? sid[0] ?? '' : sid ?? '')
  if (!author) return { ok: false, error: 'X-Sovereign-Id (author pseudonym) required' }
  return { ok: true, principal: { author } }
}
