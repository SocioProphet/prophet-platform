// Who may read the record bundle, and on what grounds.
//
// GET /api/health/twin returned the whole bundle with no authorization. The service header
// says it runs LOCAL-FIRST on the person's own node — but deploy/values routes it through
// the cockpit's nginx at /svc/health, so it is reachable, and the cockpit calls it from the
// BROWSER. A bearer token would therefore live in JavaScript, which is not authentication;
// it is authentication-shaped decoration.
//
// What actually makes the endpoint safe today is that the data is synthetic. So that is the
// thing enforced: in the default mode the twin serves freely and REFUSES the moment real
// records exist. The connector plane can land real records at any time, and when it does the
// open endpoint has to stop on its own — not when someone remembers to change a setting.
//
// 'authenticated' is for a deployment that genuinely serves a person's records: a token is
// required and its absence fails closed, so the permissive mode is something an operator
// asserts rather than something they inherit by forgetting.
//
// Pure and parameterised so it is testable without standing up a server; server.ts binds a
// port at import time, which would otherwise make the gate provable only by running it.

import { createHash, timingSafeEqual } from 'node:crypto';

export type Exposure = 'synthetic-only' | 'authenticated';

/** Constant-time compare whose control flow does not depend on either value's length.
 *
 *  `timingSafeEqual` throws on a length mismatch, so something has to handle unequal lengths
 *  before calling it. The first version of this function guarded that with an early branch —
 *  correct and necessary — but inside the branch it called `timingSafeEqual(ab, ab)`, the
 *  presented value against ITSELF, and its docstring described that as comparing "against a
 *  same-length decoy". It was not a decoy. It compared the attacker's own input to itself,
 *  discarded the result, and returned false; deleting the line would have changed nothing.
 *
 *  The practical leak was negligible: the work is proportional to the presented value in both
 *  branches, and the attacker already knows how long their own guess is. The defect is that a
 *  security primitive's comment asserted a mechanism the code did not implement — and comments
 *  on auth primitives are load-bearing, because the next reader audits the claim rather than
 *  re-deriving the bytes.
 *
 *  Digesting both sides first removes the problem instead of restating it. SHA-256 output is
 *  always 32 bytes, so the lengths can never differ: there is no throw to dodge, no branch to
 *  balance, and no decoy to owe anyone. Nothing observable depends on the secret's length or
 *  its contents. Total work still scales with the PRESENTED value's length, which is the
 *  attacker's own input — that is unavoidable (it must be read) and discloses nothing.
 *
 *  A plain digest rather than an HMAC: the digests are computed and compared inside this
 *  function and never escape it, so a keyed hash would buy nothing here. */
function timingSafeEquals(a: string, b: string): boolean {
  const ad = createHash('sha256').update(a, 'utf8').digest();
  const bd = createHash('sha256').update(b, 'utf8').digest();
  return timingSafeEqual(ad, bd);
}

export interface ExposureDenial {
  code: 401 | 403 | 503;
  body: Record<string, unknown>;
}

export interface ExposureInputs {
  mode: Exposure;
  /** Configured shared secret. Empty means none configured. */
  token: string;
  /** Raw Authorization header as presented, if any. */
  authorization: string;
  /** How many records the connector plane has actually landed. */
  ingestedRecords: number;
}

/** Read the mode from the environment. Anything but the explicit opt-in is synthetic-only. */
export function exposureFromEnv(env: NodeJS.ProcessEnv = process.env): Exposure {
  return env['HEALTH_TWIN_EXPOSURE'] === 'authenticated' ? 'authenticated' : 'synthetic-only';
}

/** Null = serve it. Otherwise the refusal, with the reason stated rather than implied. */
export function exposureDenial(input: ExposureInputs): ExposureDenial | null {
  if (input.mode === 'authenticated') {
    if (!input.token) {
      return {
        code: 503,
        body: {
          error: 'HEALTH_TWIN_EXPOSURE=authenticated but HEALTH_TWIN_TOKEN is unset — ' +
            'refusing to serve records ungoverned (fail-closed)',
        },
      };
    }
    // REQUIRE the Bearer scheme rather than stripping it when it happens to be there.
    // `replace(/^Bearer\s+/i, '')` is a no-op on a header that carries any other scheme,
    // so the entire header value was then compared as though it were the credential: a
    // bare `Authorization: <secret>` authenticated, and `Authorization: Basic <secret>`
    // was compared as the string `Basic <secret>`. Neither is a bearer credential, and an
    // auth path that accepts things it never meant to accept is one bad refactor away
    // from accepting the wrong one. Match the scheme, then take the rest as the token.
    // The token group is `\S.*`, not `.+`: `[ \t]+` and `.+` both match a space/tab, so on a header
    // like `Bearer \t\t\t…` the two quantifiers share the boundary and matching is worst-case quadratic
    // — a polynomial-ReDoS on the PHI auth path (CodeQL js/polynomial-redos, high). Requiring the token
    // to START non-whitespace makes the split unique (`\S` and `[ \t]` are disjoint), so there is nothing
    // to backtrack over. `.trim()` already stripped the outer spaces and a bearer token never begins with
    // whitespace, so nothing legitimate is lost; a whitespace-only tail still fails to match and 401s.
    const match = /^Bearer[ \t]+(\S.*)$/is.exec(input.authorization.trim());
    const presented = match ? match[1].trim() : '';
    // Constant-time. The previous note here argued a length-independent compare was not the
    // concern because the token is a deployment secret rather than a per-user credential.
    // That reasoning is weaker than it looks on THIS endpoint: it is externally reachable
    // (deploy/values routes it through the cockpit's nginx at /svc/health) and it guards
    // PHI, so an attacker gets unlimited free attempts against a single long-lived secret —
    // exactly the case where a byte-at-a-time oracle is worth having. Cheap to remove.
    if (!presented || !timingSafeEquals(presented, input.token)) {
      return { code: 401, body: { error: 'unauthorized' } };
    }
    return null;
  }

  if (input.ingestedRecords > 0) {
    return {
      code: 403,
      body: {
        error: 'refusing to serve the record bundle: this instance holds ingested records ' +
          'and is running in synthetic-only exposure',
        ingestedRecords: input.ingestedRecords,
        remedy: 'set HEALTH_TWIN_EXPOSURE=authenticated and provision HEALTH_TWIN_TOKEN, or ' +
          'run this twin local-first and stop routing it publicly',
      },
    };
  }
  return null;
}
