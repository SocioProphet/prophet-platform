// WHO is holding this grant — the difference between a capability and a credential.
//
// resolveGrant() answers three questions: does this id exist, is it unrevoked, is it unexpired.
// It never asks who is presenting it. That makes a grant id a BEARER CAPABILITY: possession is
// authorization. And the id travelled in a query string, which is the one place a secret cannot
// survive — it lands in access logs, proxy logs, browser history and the `Referer` header of every
// outbound link from the page that used it. One of them (the demo seed) was additionally hard-coded
// in server.ts, so "read the source" was a valid way to obtain a chart.
//
// So the grant now BINDS to a holder. At issue time the server mints a 256-bit secret, stores only
// its sha256 digest on the grant, and returns the secret ONCE. Reading through the grant means
// presenting `<grant-id>.<secret>` in a request header; the server hashes what was presented and
// compares digests in constant time. The id alone stops being sufficient — which is the whole defect.
//
// WHAT THIS IS NOT. This authenticates the HOLDER OF A SECRET. It does not authenticate a person, an
// organisation or a clinician licence: there is no identity provider, no key directory and no PKI in
// this estate, and inventing one here would be authentication-shaped decoration of exactly the kind
// exposure.ts refuses to ship. If the secret is forwarded, the forwardee is the holder. That is
// stated in HOLDER_AUTH_DISCLOSURE and returned on every authenticated read, in the same spirit as
// deident.ts recording `keyed:false` rather than implying a protection it does not have.
//
// WHY A DEDICATED HEADER AND NOT `Authorization`. `Authorization` is already spoken for: exposure.ts
// reads it for the DEPLOYMENT token that decides whether this instance may serve records at all.
// Those are two different questions with two different lifetimes and two different holders (an
// operator; a clinician), and an `authenticated`-mode deployment needs BOTH presented on the same
// request. Stacking them on one header is how a service ends up checking one and believing it
// checked the other. A request header is equally safe from the leak channels that motivated this
// change: unlike a query string it is not in the request line, so it is not in access logs, not in
// `Referer`, and not in browser history.
//
// Pure and parameterised — no http, no process state — so the gate is provable without binding a
// port. server.ts binds at import time, which would otherwise make this testable only by running it.
import { createHash, randomBytes, timingSafeEqual } from 'node:crypto';

/** Lower-case, because node lower-cases incoming header names. */
export const HOLDER_HEADER = 'x-health-grant';

/** What this module needs of a grant. The secret itself is never stored, so it is not in this shape. */
export interface HolderBound {
  id: string;
  /** `sha256-<64 hex>` of the holder secret. Absent = the grant binds nobody and can authenticate nobody. */
  holderDigest?: string;
}

export type HolderAuth =
  | { ok: true; grantId: string; holderDigest: string }
  | { ok: false; code: 401; reason: string; detail?: string };

/**
 * What the caller is told about the authentication they just passed. Returned on the read itself:
 * a surface that shows a chart should be able to show what stands behind it without reading this file.
 */
export const HOLDER_AUTH_DISCLOSURE = {
  mechanism: 'grant-holder-secret',
  binds: 'the holder of a per-grant secret minted at issue time and shown once',
  verifier: 'sha256 digest, constant-time compare; the secret itself is never stored',
  /** No identity provider, no key directory, no PKI. A forwarded secret makes the forwardee the holder. */
  identityVerified: false,
  /** The credential is presented in a header, so it is not in the request line, logs or `Referer`. */
  channel: `request header ${HOLDER_HEADER}`,
} as const;

/** 256 bits from the CSPRNG. base64url so it survives a header, a shell and a URL unescaped. */
export function mintHolderSecret(): string {
  return randomBytes(32).toString('base64url');
}

/** The only form of the secret that is ever written down. */
export function holderDigest(secret: string): string {
  return `sha256-${createHash('sha256').update(secret, 'utf8').digest('hex')}`;
}

/** What the holder presents: the id (so the server can find the grant) joined to the secret. */
export function holderToken(grantId: string, secret: string): string {
  return `${grantId}.${secret}`;
}

/**
 * Split on the LAST dot: grant ids contain dashes and hex, never a dot, while base64url secrets
 * contain `-` and `_` but also never a dot. Splitting on the first dot would break the moment an id
 * scheme grows one.
 */
export function parseHolderToken(raw: string): { grantId: string; secret: string } | null {
  const t = (raw ?? '').trim();
  if (!t) return null;
  const i = t.lastIndexOf('.');
  if (i <= 0 || i === t.length - 1) return null;
  return { grantId: t.slice(0, i), secret: t.slice(i + 1) };
}

/** Pull the presented token out of a node headers object (array-valued headers take the first). */
export function presentedHolderToken(headers: Record<string, string | string[] | undefined>): string {
  const h = headers?.[HOLDER_HEADER];
  return String((Array.isArray(h) ? h[0] : h) ?? '').trim();
}

export const HOLDER_REQUIRED = 'grant holder credential required';
/**
 * ONE reason for every authentication failure that involves a real credential attempt: unknown id,
 * unbound grant, wrong secret. Distinguishing them would turn this endpoint into an oracle that
 * confirms which grant ids exist and are bound — to a caller who has, by definition, just failed to
 * authenticate. Grant STATE (revoked / expired) is reported with its reason, but only to a holder who
 * has already proved they hold the grant.
 */
export const HOLDER_FAILED = 'grant holder authentication failed';

export interface HolderAuthInput {
  /** Raw header value as presented. */
  presented: string;
  /** Grant lookup by id. Returns undefined for unknown ids. */
  find: (id: string) => HolderBound | undefined;
  /** Optional sink for the operator-facing detail that must not go on the wire. */
  onUnbound?: (grantId: string) => void;
}

/** Fails closed: every path that is not a proven digest match is a refusal. */
export function authenticateHolder(input: HolderAuthInput): HolderAuth {
  if (!input.presented) {
    return {
      ok: false, code: 401, reason: HOLDER_REQUIRED,
      detail: `present the grant as \`${HOLDER_HEADER}: <grant-id>.<secret>\` — the id on its own is not a credential`,
    };
  }
  const parsed = parseHolderToken(input.presented);
  if (!parsed) {
    return {
      ok: false, code: 401, reason: 'malformed grant holder credential',
      detail: `expected \`${HOLDER_HEADER}: <grant-id>.<secret>\``,
    };
  }
  const g = input.find(parsed.grantId);
  if (!g) return { ok: false, code: 401, reason: HOLDER_FAILED };
  if (!g.holderDigest) {
    // A grant minted before holder binding existed authenticates nobody. It does not get a pass for
    // being old. The operator-facing reason goes to the log, not to the caller who just failed.
    input.onUnbound?.(parsed.grantId);
    return { ok: false, code: 401, reason: HOLDER_FAILED };
  }
  if (!constantTimeEqual(g.holderDigest, holderDigest(parsed.secret))) {
    return { ok: false, code: 401, reason: HOLDER_FAILED };
  }
  return { ok: true, grantId: parsed.grantId, holderDigest: g.holderDigest };
}

/**
 * Both sides are `sha256-<64 hex>`, so they are the same length whenever the stored value is
 * well-formed; the length guard exists for a malformed record, not for a secret, and returning early
 * on it leaks nothing about the secret.
 */
function constantTimeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a, 'utf8');
  const bb = Buffer.from(b, 'utf8');
  if (ab.length !== bb.length) return false;
  return timingSafeEqual(ab, bb);
}

// ── boot-time policy: the demo seed, and the legacy query form ──────────────────────────────────
// Both of these are conveniences that are safe only while the data is synthetic. Neither is allowed
// to be a comment: the server REFUSES TO BOOT if either is asked for in a deployment that has
// declared it serves real records. A configuration that cannot exist cannot be forgotten about.

export type Exposure = 'synthetic-only' | 'authenticated';

export interface SeedDecision {
  seed: boolean;
  /** Non-empty = refuse to boot, with this stated. */
  fatal?: string;
  /** Present only when seeding. Never a literal in source. */
  secret?: string;
  /** true = freshly minted this boot (so it must be printed once); false = supplied by the operator. */
  minted?: boolean;
  why: string;
}

/**
 * The demo cardiologist grant. It used to be an unconditional array literal in server.ts with a
 * well-known id, which meant every deployment shipped a live grant whose "credential" was a string
 * printed in a public repository. Now: absent unless explicitly asked for, never valid in an
 * `authenticated` deployment, and its secret is either supplied by the operator or minted at boot.
 */
export function seedGrantDecision(env: NodeJS.ProcessEnv, exposure: Exposure): SeedDecision {
  if (env['HEALTH_TWIN_SEED_GRANT'] !== '1') {
    return { seed: false, why: 'HEALTH_TWIN_SEED_GRANT is not "1" — no demo grant is seeded (default)' };
  }
  if (exposure === 'authenticated') {
    return {
      seed: false,
      fatal: 'HEALTH_TWIN_SEED_GRANT=1 with HEALTH_TWIN_EXPOSURE=authenticated: a demo consent grant ' +
        'cannot exist on a deployment that serves real records. Refusing to boot.',
      why: 'demo seed requested in an authenticated deployment',
    };
  }
  const supplied = String(env['HEALTH_TWIN_SEED_GRANT_SECRET'] ?? '').trim();
  return supplied
    ? { seed: true, secret: supplied, minted: false, why: 'demo seed with an operator-supplied holder secret' }
    : { seed: true, secret: mintHolderSecret(), minted: true, why: 'demo seed with a holder secret minted this boot' };
}

export interface LegacyQueryDecision {
  allowed: boolean;
  fatal?: string;
  why: string;
}

/**
 * `?grant=<id>` — the leak channel itself. Refused by default. An operator running the synthetic
 * demo can re-enable it for compatibility with the cockpit's current fetch calls, and gets a
 * `Warning` header and a deprecation block on every use; a deployment that has declared it serves
 * real records cannot enable it at all.
 */
export function legacyQueryDecision(env: NodeJS.ProcessEnv, exposure: Exposure): LegacyQueryDecision {
  if (env['HEALTH_TWIN_LEGACY_GRANT_QUERY'] !== '1') {
    return { allowed: false, why: 'grant ids are not accepted in the query string (default)' };
  }
  if (exposure === 'authenticated') {
    return {
      allowed: false,
      fatal: 'HEALTH_TWIN_LEGACY_GRANT_QUERY=1 with HEALTH_TWIN_EXPOSURE=authenticated: a grant id in a ' +
        'query string is logged by every proxy in the path and leaks in `Referer`. Refusing to boot.',
      why: 'legacy query form requested in an authenticated deployment',
    };
  }
  return { allowed: true, why: 'DEPRECATED legacy query form enabled for the synthetic demo' };
}

export const LEGACY_QUERY_REFUSAL = 'grant ids are not accepted in the query string';
export const LEGACY_QUERY_DETAIL =
  `a query string is written to access logs, proxy logs, browser history and \`Referer\` — present the ` +
  `grant as \`${HOLDER_HEADER}: <grant-id>.<secret>\` instead`;
export const LEGACY_QUERY_WARNING =
  `299 - "deprecated: grant id in query string; use the ${HOLDER_HEADER} header. This form is unauthenticated ` +
  `and is refused unless HEALTH_TWIN_LEGACY_GRANT_QUERY=1 on a synthetic-only deployment."`;
