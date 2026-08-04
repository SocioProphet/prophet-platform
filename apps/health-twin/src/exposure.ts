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
 *  SHA-256 output is always 32 bytes, so the lengths can never differ: there is no `timingSafeEqual`
 *  throw to dodge, no branch to balance, and no decoy to owe anyone. Nothing observable depends on the
 *  secret's length or contents; total work scales only with the presented value, which the attacker
 *  already controls. A plain digest, not an HMAC — the digests are computed and compared here and
 *  never escape this function. (Back-ported from prophet-platform #1086/#1109 into the canonical.) */
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
    // `replace(/^Bearer\s+/i, '')` was a no-op on a header carrying any other scheme, so the whole
    // value was then compared as the credential: a bare `Authorization: <secret>` authenticated, and
    // `Authorization: Basic <secret>` was compared as the string `Basic <secret>`. Neither is a bearer
    // credential. Match the scheme, then take the rest. The token group is `\S.*`, not `.+`, so `[ \t]+`
    // and the token do not share a character class and `Bearer\t\t…` cannot backtrack quadratically
    // (polynomial ReDoS) on this externally reachable PHI read gate.
    const match = /^Bearer[ \t]+(\S.*)$/is.exec(input.authorization.trim());
    const presented = match ? match[1].trim() : '';
    // Constant-time. This endpoint is reachable cross-origin (nginx /svc/health) and guards PHI, so an
    // attacker gets unlimited free attempts against one long-lived secret — exactly the case where a
    // byte-at-a-time timing oracle is worth removing, deployment secret or not.
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
