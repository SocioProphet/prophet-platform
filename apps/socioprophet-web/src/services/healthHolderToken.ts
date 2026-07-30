// The grant HOLDER CREDENTIAL — `<grant-id>.<secret>` — and the only place this app is allowed to
// keep one: a module-scoped ref, i.e. the JavaScript heap of this tab, for as long as this tab lives.
//
// WHY THE CREDENTIAL EXISTS AT ALL. A grant id used to be the whole credential, presented as
// `?grant=<id>`. Possession was authorization, and the channel wrote the id into access logs, proxy
// logs, browser history and the `Referer` of every outbound link. The engine now binds each grant to
// a 256-bit secret minted at issue time, stores only its sha256 digest, and reads it from the
// `x-health-grant` request header. See apps/health-twin/src/grantauth.ts.
//
// WHY NOT localStorage / sessionStorage / a cookie — the three obvious places, all refused:
//   • localStorage survives the browser being closed, so the credential outlives the clinician's
//     shift and stays on a shared bedside iPad for the next person who opens the cockpit. It is also
//     readable by any script that ever runs on this origin, which turns one XSS into a chart.
//   • sessionStorage is narrower (per tab, cleared on close) but has the same XSS reachability and
//     still survives a reload — so "I walked away and the tab was still open" still reads the chart.
//   • a cookie is worse than both: it is attached to requests automatically, which is precisely the
//     ambient-authority property that made the query-string form dangerous, and it would ride along
//     on requests this app never intended to authenticate.
// The heap is not immune to XSS either — nothing in a browser is — but it is the smallest window we
// can offer: no persistence, no automatic attachment, and gone the moment the tab goes.
//
// WHY LOSING IT ON REFRESH IS CORRECT. A credential that survives a refresh is a credential left
// behind on a shared machine. Re-entry is a two-second cost paid by the clinician; persistence is an
// open chart paid for by the patient. The UI says so in as many words rather than treating it as a
// papercut to engineer around.
//
// A browser also cannot safely hold a long-lived per-grant secret that WE choose — which is why
// there is no build-time token here, no `VITE_HEALTH_GRANT_TOKEN`, and nothing to commit. The secret
// is the clinician's, supplied per session. apps/health-twin/src/exposure.ts is the standing refusal
// of the alternative.
import { computed, ref } from 'vue';

/** The header the engine reads the credential from (grantauth.ts: HOLDER_HEADER). */
export const HOLDER_HEADER = 'x-health-grant';

/**
 * Module scope, deliberately: it outlives any single component (the doctor chart is a tab that
 * unmounts every time the clinician looks at something else) and dies with the tab. Not exported —
 * `holderHeader()` is the only reader, so there is exactly one call site to audit.
 */
const token = ref('');

/** Whether a credential is held for this session. */
export const hasHolderToken = computed(() => token.value.length > 0);

/**
 * The grant-id half of the held token: everything before the LAST dot, mirroring the server's
 * `parseHolderToken()` (ids carry dashes and hex, secrets are base64url — neither contains a dot).
 * The id is not the secret; it is safe to render, and naming the grant being read is the whole point
 * of showing it. The half after the dot is never returned by anything in this module.
 */
export const holderGrantId = computed(() => {
  const i = token.value.lastIndexOf('.');
  return i > 0 ? token.value.slice(0, i) : '';
});

/**
 * Accept a pasted credential. Shape-checks it the same way the server does, so an obviously wrong
 * paste (a bare grant id, most likely) is caught here instead of being spent as a failed
 * authentication attempt against the engine.
 *
 * @returns false when the input is not `<id>.<secret>`; the held token is left untouched.
 */
export function setHolderToken(raw: string): boolean {
  const t = (raw ?? '').trim();
  const i = t.lastIndexOf('.');
  if (i <= 0 || i === t.length - 1) return false;
  token.value = t;
  return true;
}

/** Drop the credential. Called on sign-off, on a refusal, and by the explicit "forget" control. */
export function clearHolderToken(): void {
  token.value = '';
}

/**
 * The ONE reader. Returns the header to merge into a fetch, or null when nothing is held — callers
 * that get null must not make the request at all, rather than sending an unauthenticated one that
 * would 401 and write a failed read into the engine's receipt trail for no reason.
 */
export function holderHeader(): Record<string, string> | null {
  return token.value ? { [HOLDER_HEADER]: token.value } : null;
}
