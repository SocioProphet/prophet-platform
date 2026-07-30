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

import { timingSafeEqual } from 'node:crypto';

export type Exposure = 'synthetic-only' | 'authenticated';

/** Constant-time string compare. timingSafeEqual throws on a length mismatch, which would
 *  itself leak the length, so unequal lengths are compared against a same-length decoy and
 *  always answer false. */
function timingSafeEquals(a: string, b: string): boolean {
  const ab = Buffer.from(a, 'utf8');
  const bb = Buffer.from(b, 'utf8');
  if (ab.length !== bb.length) {
    timingSafeEqual(ab, ab);
    return false;
  }
  return timingSafeEqual(ab, bb);
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
