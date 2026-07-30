// WHICH ORIGINS may drive this engine from a browser.
//
// `send()` set `access-control-allow-origin: *` on every response, and the holder-credential change
// added `x-health-grant` to `access-control-allow-headers`. Read those two lines together and they
// say: ANY web page on the internet may call this engine, set the credential header, and READ THE
// REPLY. On a synthetic-only deployment minting is ungated, so a page the patient merely visits could
// POST /api/health/grant, take the one-shot secret out of a response it is allowed to read, and pull
// the chart cross-origin — without a single leaked id. Introducing a credential and simultaneously
// making it usable from anywhere hands back exactly what the credential was for. `*` was survivable
// while `content-type` was the only allowed header; it stopped being survivable in the same commit
// that made a credential presentable.
//
// THE POLICY. `*` is not a value this service will emit, and not a value an operator can configure.
// A browser origin is allowed only if it is named, exactly, in the allowlist; anything else gets NO
// `access-control-allow-origin` at all and the browser refuses to hand the response to the page.
//
// WHAT THIS DOES AND DOES NOT BUY. CORS is enforced by the browser, not by us: `curl` and any
// server-side client ignore all of this, and always could. What it stops is the DRIVE-BY — a page in
// a tab the patient already has open using the patient's own network position. It is not a substitute
// for the exposure membrane or for holder authentication, and it is not claimed as one.
//
// NO CREDENTIALS MODE. `access-control-allow-credentials` is deliberately never sent. The holder
// credential is an explicit header the caller has to set, not ambient authority the browser attaches;
// keeping cookies out of the picture is the same reasoning that put the credential in a header
// instead of the query string.
//
// Pure and parameterised — no http, no process state — so the policy is provable without binding a
// port, exactly as exposure.ts and grantauth.ts are.
import { HOLDER_HEADER } from './grantauth.js';

export type Exposure = 'synthetic-only' | 'authenticated';

/** Never `*`, and never the two credential-bearing verbs without an origin match. */
export const CORS_ALLOW_HEADERS = `content-type, authorization, ${HOLDER_HEADER}`;
export const CORS_ALLOW_METHODS = 'POST, GET, OPTIONS';

/**
 * Local development and the BearBrowser sovereign embedding are the only browser callers that are
 * genuinely cross-origin. The DEPLOYED cockpit is not: nginx proxies `/svc/health/` to this service,
 * so those requests are same-origin and never consult CORS at all (see apps/socioprophet-web/
 * nginx.conf and vite.config.ts). That is why this list is short, and why an empty list breaks
 * nothing in the cluster.
 *
 * 5174 is the cockpit's vite dev server; 8080 is its nginx container port when run locally.
 * Anything else — including a BearBrowser sovereign host on some other loopback port — has to be
 * named in HEALTH_TWIN_ALLOWED_ORIGINS. Guessing a wider default is how `*` happened.
 */
export const DEV_ORIGINS: readonly string[] = [
  'http://localhost:5174', 'http://127.0.0.1:5174',
  'http://localhost:8080', 'http://127.0.0.1:8080',
];

export interface OriginPolicy {
  origins: string[];
  /** Non-empty = refuse to boot, with this stated. */
  fatal?: string;
  why: string;
}

/**
 * `HEALTH_TWIN_ALLOWED_ORIGINS` — comma-separated EXACT origins (`scheme://host[:port]`), and it is
 * authoritative whenever the variable is PRESENT, including when it is empty: `""` means "no browser
 * origin at all", which an operator must be able to say out loud. (Treating empty as unset would
 * silently reinstate the dev defaults on the deployment that had just asked for none.) Absent:
 *
 *   • `synthetic-only` → the loopback dev origins above, because the data is synthetic and a
 *     developer should not have to configure CORS to run the thing;
 *   • `authenticated`  → NOTHING. A deployment that has declared it serves real records names the
 *     browsers that may drive it, or serves none of them. The default cockpit path does not need it.
 *
 * `*` is FATAL AT BOOT in either mode. This whole module exists because that value was reachable;
 * leaving it configurable would move the defect from a line of code to a line of YAML. A
 * configuration that cannot exist cannot be forgotten about — the same rule seedGrantDecision() and
 * legacyQueryDecision() already apply.
 */
export function corsPolicyFromEnv(env: NodeJS.ProcessEnv, exposure: Exposure): OriginPolicy {
  const declared = env['HEALTH_TWIN_ALLOWED_ORIGINS'];
  if (declared !== undefined) {
    const listed = String(declared).split(',').map((s) => s.trim()).filter(Boolean);
    if (listed.length === 0) return { origins: [], why: 'HEALTH_TWIN_ALLOWED_ORIGINS is empty — no browser origin is allowed' };
    if (listed.includes('*')) {
      return {
        origins: [],
        fatal: 'HEALTH_TWIN_ALLOWED_ORIGINS contains "*": a wildcard origin on a service that accepts ' +
          `the \`${HOLDER_HEADER}\` credential lets any page on the internet mint a grant and read the ` +
          'chart from the visitor\'s own browser. Name the cockpit origins explicitly. Refusing to boot.',
        why: 'wildcard origin requested',
      };
    }
    const bad = listed.filter((o) => !isOrigin(o));
    if (bad.length) {
      return {
        origins: [],
        fatal: `HEALTH_TWIN_ALLOWED_ORIGINS holds ${bad.length} value(s) that are not an origin ` +
          `(${bad.join(', ')}). An origin is \`scheme://host[:port]\` with no path, no trailing slash ` +
          'and no wildcard — a value that never matches is a silent outage. Refusing to boot.',
        why: 'malformed origin in the allowlist',
      };
    }
    return { origins: [...new Set(listed)], why: `${listed.length} origin(s) allowed from HEALTH_TWIN_ALLOWED_ORIGINS` };
  }
  if (exposure === 'authenticated') {
    return {
      origins: [],
      why: 'no browser origin is allowed (authenticated deployment, HEALTH_TWIN_ALLOWED_ORIGINS unset) — ' +
        'the cockpit reaches this service same-origin through the nginx /svc/health proxy',
    };
  }
  return { origins: [...DEV_ORIGINS], why: 'loopback development origins (synthetic-only default)' };
}

/** `scheme://host[:port]`, nothing else. Rejects `*`, paths, trailing slashes and bare hostnames. */
export function isOrigin(value: string): boolean {
  if (!/^https?:\/\/[^/?#*\s]+$/.test(value)) return false;
  try { return new URL(value).origin === value; } catch { return false; }
}

/**
 * The CORS headers for one response. `origin` is the request's `Origin` header, absent for
 * same-origin and non-browser callers — who get no CORS headers, because they never look at them.
 *
 * `vary: origin` goes on EVERY response, allowed or not: the reply now depends on the request's
 * origin, and a cache that does not know that will hand one origin's allowance to another.
 */
export function corsHeaders(origin: string | undefined, allowed: ReadonlySet<string>): Record<string, string> {
  const o = (origin ?? '').trim();
  if (!o) return { vary: 'origin' };
  if (!allowed.has(o)) return { vary: 'origin' }; // no ACAO — the browser refuses to expose the reply
  return {
    vary: 'origin',
    'access-control-allow-origin': o,
    'access-control-allow-headers': CORS_ALLOW_HEADERS,
    'access-control-allow-methods': CORS_ALLOW_METHODS,
  };
}

/** True only for an origin that was named. An absent Origin is not a browser and is not "allowed". */
export function originAllowed(origin: string | undefined, allowed: ReadonlySet<string>): boolean {
  const o = (origin ?? '').trim();
  return !!o && allowed.has(o);
}
