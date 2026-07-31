/**
 * Grant HOLDER AUTHENTICATION in the cockpit — the client half of prophet-platform#1081.
 *
 * The engine stopped accepting a grant id as a credential: `?grant=<id>` is refused with 401 because
 * a query string lands in access logs, proxy logs, browser history and `Referer`. Reads now present
 * `x-health-grant: <grant-id>.<secret>`, verified against a stored sha256 digest.
 *
 * These are the three proofs that the cockpit half is honest, plus the two that keep it honest:
 *
 *   1. NO TOKEN  → the empty state renders and NOT ONE request goes out that the engine would 401.
 *                  (The old chart fired doctor-view at mount with whatever grant id came first.)
 *   2. GOOD TOKEN→ doctor-view, evidence and agent-read all succeed, all three on the header, and
 *                  no request URL anywhere carries `grant=`.
 *   3. BAD TOKEN → the 401 surfaces as the recoverable "enter your token" state — not a crash, not a
 *                  generic error toast, and not a silently blank chart.
 *   4. The credential never reaches localStorage, sessionStorage or document.cookie.
 *   5. `holderBound` is rendered as a visible difference, so a grant that can authenticate someone
 *      does not look identical to one that cannot.
 */
import { mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import DoctorChart from '../pages/DoctorChart.vue';
import { clearHolderToken } from '../services/healthHolderToken';

const GOOD = 'grant-abc123.s3cr3t-token-value';
const BAD = 'grant-abc123.wrong-secret';

const GRANTS = {
  grants: [
    { id: 'grant-abc123', agent: 'Dr. A. Rivera (Cardiology)', scope: 'cardiometabolic', scopeSummary: 'cardiometabolic · 2y', active: true, holderBound: true, expires_at: '2026-12-01T00:00:00.000Z', reads: 2 },
    { id: 'grant-legacy', agent: 'Dr. Old Grant', scope: 'all systems', scopeSummary: 'full history', active: true, holderBound: false, expires_at: '2026-12-01T00:00:00.000Z', reads: 0 },
  ],
  presets: {},
};

const VIEW = {
  grant: { id: 'grant-abc123', agent: 'Dr. A. Rivera (Cardiology)', scope: 'cardiometabolic', scopeSummary: 'cardiometabolic · 2y', expires_at: '2026-12-01T00:00:00.000Z', reads: 3 },
  view: {
    subject: { id: 'subj-1', label: 'Synthetic Subject', note: '', ageBand: '45-54', sex: 'F' },
    systems: [{ id: 'cardiovascular', label: 'Cardiovascular', organs: ['heart'], observations: [], conditions: [], encounters: [], imaging: [] }],
    timeline: [], counts: { observations: 0, conditions: 0, encounters: 0, imaging: 0 },
    medications: [], allergies: [], immunizations: [], careTeam: [], readings: [],
    disclaimer: 'non-diagnostic',
  },
  withheld: { total: 4, conditions: 4 },
  receipt: { id: 'ht-doctor-read-abcdef' },
};

const REFUSAL = { blocked: true, authenticated: false, reason: 'grant holder authentication failed' };

/** Every request the component made: url + the credential header, if any. */
let calls: { url: string; token?: string }[] = [];

function installFetch(token: string | null) {
  calls = [];
  const fetchMock = vi.fn(async (input: any, init: any = {}) => {
    const url = String(input);
    const headers = (init.headers ?? {}) as Record<string, string>;
    const presented = headers['x-health-grant'];
    calls.push({ url, token: presented });

    if (url.includes('/api/health/grants')) return json(200, GRANTS);

    // The engine's rule, reproduced: these routes require a valid holder credential.
    if (url.includes('/api/health/doctor-view') || url.includes('/api/health/evidence') || url.includes('/api/health/agent-read')) {
      if (!presented) return json(401, { blocked: true, reason: 'grant holder credential required' });
      if (presented !== GOOD) return json(401, REFUSAL);
      if (url.includes('/api/health/doctor-view')) return json(200, VIEW);
      if (url.includes('/api/health/evidence')) return json(200, { context: 'cardiometabolic', items: [] });
      return json(200, { agent: 'Dr. A. Rivera (Cardiology)', reads: 4, receipt: { id: 'ht-read-1' } });
    }
    return json(200, {});
  });
  vi.stubGlobal('fetch', fetchMock);
  if (token) {
    // Enter it the way a clinician does — through the component's own input.
    return token;
  }
  return null;
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

/** Type a token into the chart's credential field and submit it. */
async function enterToken(w: any, token: string) {
  await w.find('.dc-auth-in').setValue(token);
  await w.find('.dc-auth-go').trigger('click');
  await flush();
}

const flush = async () => { for (let i = 0; i < 6; i++) await new Promise((r) => setTimeout(r, 0)); };

beforeEach(() => { clearHolderToken(); });
afterEach(() => { clearHolderToken(); vi.unstubAllGlobals(); });

describe('doctor chart · grant holder authentication', () => {
  it('1. with NO token: shows the enter-token empty state and makes no request that would 401', async () => {
    installFetch(null);
    const w = mount(DoctorChart);
    await flush();

    // the recoverable state, not an error and not a chart
    expect(w.find('.dc-auth').exists()).toBe(true);
    expect(w.find('.dc-auth-h').text()).toContain('Enter your grant token');
    expect(w.find('.dc-err').exists()).toBe(false);
    expect(w.find('.dc-head').exists()).toBe(false);

    // the ONLY call is the unauthenticated grants list, which the engine serves to anyone
    expect(calls.map((c) => c.url.replace(/^.*\/api/, '/api'))).toEqual(['/api/health/grants']);
    expect(calls.some((c) => c.url.includes('doctor-view'))).toBe(false);
    expect(calls.some((c) => c.url.includes('/api/health/evidence'))).toBe(false);
  });

  it('1b. the empty state says the token is session-only and that losing it on refresh is intended', async () => {
    installFetch(null);
    const w = mount(DoctorChart);
    await flush();
    const copy = w.find('.dc-auth').text();
    expect(copy).toContain('in memory for this session only');
    expect(copy).toMatch(/Refreshing the page loses it, and that is deliberate/);
  });

  it('2. with a VALID token: doctor-view, evidence and agent-read all go through on the header', async () => {
    installFetch(null);
    const w = mount(DoctorChart);
    await flush();
    await enterToken(w, GOOD);

    // the chart rendered
    expect(w.find('.dc-auth').exists()).toBe(false);
    expect(w.find('.dc-head').exists()).toBe(true);
    expect(w.find('.dc-gate').text()).toContain('Dr. A. Rivera (Cardiology)');

    const dv = calls.find((c) => c.url.includes('doctor-view'));
    const ev = calls.find((c) => c.url.includes('/api/health/evidence'));
    expect(dv?.token).toBe(GOOD);
    expect(ev?.token).toBe(GOOD);

    // agent-read is exercised directly against the same credential
    const { agentRead } = await import('../services/healthTwinApi');
    const r = await agentRead();
    expect(r.receipt?.id).toBe('ht-read-1');
    expect(calls.find((c) => c.url.includes('agent-read'))?.token).toBe(GOOD);
  });

  it('2b. NO request ever carries the grant in the URL — the `?grant=` form is gone', async () => {
    installFetch(null);
    const w = mount(DoctorChart);
    await flush();
    await enterToken(w, GOOD);

    const { agentRead } = await import('../services/healthTwinApi');
    await agentRead();

    expect(calls.length).toBeGreaterThan(2);
    for (const c of calls) {
      expect(c.url).not.toContain('grant=');
      expect(c.url).not.toContain('s3cr3t');
    }
  });

  it('3. with a BAD token: the 401 is the recoverable enter-token state, not a crash or a blank chart', async () => {
    installFetch(null);
    const w = mount(DoctorChart);
    await flush();
    await enterToken(w, BAD);

    // back to the credential prompt, flagged as a refusal, with the engine's reason shown
    expect(w.find('.dc-auth').exists()).toBe(true);
    expect(w.find('.dc-auth').classes()).toContain('refused');
    expect(w.find('.dc-auth-h').text()).toContain('refused');
    expect(w.find('.dc-auth-why').text()).toContain('grant holder authentication failed');

    // NOT a generic error, and NOT the 403 "access blocked" panel (that means a proven holder)
    expect(w.find('.dc-err').exists()).toBe(false);
    expect(w.find('.dc-blocked').exists()).toBe(false);
    // the input is offered again, so it is recoverable in place
    expect(w.find('.dc-auth-in').exists()).toBe(true);

    // and the refused credential was dropped rather than kept to re-fail
    const { hasHolderToken } = await import('../services/healthHolderToken');
    expect(hasHolderToken.value).toBe(false);

    // recovery actually works: entering the right one from that same state opens the chart
    await enterToken(w, GOOD);
    expect(w.find('.dc-head').exists()).toBe(true);
  });

  it('3b. a bare grant id is rejected client-side, without spending a failed authentication', async () => {
    installFetch(null);
    const w = mount(DoctorChart);
    await flush();
    const before = calls.length;
    await enterToken(w, 'grant-abc123'); // no `.secret` — not a credential
    expect(w.find('.dc-auth').classes()).toContain('refused');
    expect(calls.length).toBe(before); // nothing was sent
  });

  it('4. the credential never lands in localStorage, sessionStorage or a cookie', async () => {
    installFetch(null);
    const w = mount(DoctorChart);
    await flush();
    await enterToken(w, GOOD);

    expect(JSON.stringify(localStorage)).not.toContain('s3cr3t');
    expect(JSON.stringify(sessionStorage)).not.toContain('s3cr3t');
    expect(document.cookie).not.toContain('s3cr3t');
    // and it is not left sitting in the DOM input either
    expect(w.html()).not.toContain('s3cr3t');
  });

  it('5. holderBound is a visible difference: a grant that authenticates nobody is marked as such', async () => {
    installFetch(null);
    const w = mount(DoctorChart);
    await flush();

    const badges = w.findAll('.dc-gr-badge');
    expect(badges.length).toBe(2);
    expect(badges[0].classes()).toContain('bound');
    expect(badges[0].text()).toContain('holder-bound');
    expect(badges[1].classes()).toContain('unbound');
    expect(badges[1].text()).toContain('authenticates nobody');
    // the two are not presented identically
    expect(badges[0].text()).not.toBe(badges[1].text());
    expect(w.find('.dc-gr-note').exists()).toBe(true);
  });
});
