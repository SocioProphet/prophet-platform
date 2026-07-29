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

export type Exposure = 'synthetic-only' | 'authenticated';

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
    const presented = input.authorization.replace(/^Bearer\s+/i, '').trim();
    // Length-independent compare is not the concern here (the token is a deployment secret,
    // not a per-user credential); an empty presented value must simply never match.
    if (!presented || presented !== input.token) {
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
