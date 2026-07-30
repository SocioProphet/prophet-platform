/**
 * The PATIENT half of grant holder authentication (prophet-platform#1081) — the sharing panel.
 *
 * Issuing a grant now mints a secret and returns it ONCE as `holder.token`; only its sha256 digest
 * is stored, so it can never be looked up again. Three things have to be true on this surface:
 *
 *   1. the token is shown once, plainly labelled as unrecoverable, and is not written anywhere;
 *   2. `holderBound` is a visible difference — a grant that authenticates nobody is not rendered
 *      identically to one that does;
 *   3. "exercise this grant" is DISABLED for any grant whose token this session does not hold. The
 *      patient does not hold the clinician's secret, and the button must say so rather than fail.
 */
import { mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import HealthTwin from '../pages/HealthTwin.vue';
import { clearHolderToken } from '../services/healthHolderToken';

const MINTED = 'grant-fresh999.mInTeD-s3cr3t-value';

const TWIN = {
  subject: { id: 'subj-1', label: 'Synthetic Subject', note: '', ageBand: '45-54', sex: 'F' },
  systems: [{ id: 'cardiovascular', label: 'Cardiovascular', organs: ['heart'], observations: [], conditions: [], encounters: [], imaging: [] }],
  timeline: [], counts: { observations: 0, conditions: 0, encounters: 0, imaging: 0 },
  medications: [], allergies: [], immunizations: [], careTeam: [], readings: [],
  grants: [
    { id: 'grant-bound1', agent: 'Dr. Bound', scope: 'cardiometabolic', granted_at: '2026-01-01T00:00:00.000Z', expires_at: '2026-12-01T00:00:00.000Z', revoked: false, reads: 1, receipt: 'ht-g1', active: true },
    { id: 'grant-legacy', agent: 'Dr. Legacy', scope: 'all systems', granted_at: '2026-01-01T00:00:00.000Z', expires_at: '2026-12-01T00:00:00.000Z', revoked: false, reads: 0, receipt: 'ht-g2', active: true },
  ],
  disclaimer: 'non-diagnostic',
};

const GRANTS = {
  grants: [
    { id: 'grant-bound1', agent: 'Dr. Bound', scope: 'cardiometabolic', scopeSummary: 'cardiometabolic', active: true, holderBound: true, expires_at: '2026-12-01T00:00:00.000Z', reads: 1 },
    { id: 'grant-legacy', agent: 'Dr. Legacy', scope: 'all systems', scopeSummary: 'full history', active: true, holderBound: false, expires_at: '2026-12-01T00:00:00.000Z', reads: 0 },
  ],
  presets: {},
};

const json = (status: number, b: unknown) => new Response(JSON.stringify(b), { status, headers: { 'content-type': 'application/json' } });
const flush = async () => { for (let i = 0; i < 8; i++) await new Promise((r) => setTimeout(r, 0)); };

let calls: { url: string; token?: string }[] = [];

beforeEach(() => {
  clearHolderToken();
  localStorage.setItem('health-twin-optin-v1', '1'); // past the opt-in gate
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (input: any, init: any = {}) => {
    const url = String(input);
    calls.push({ url, token: ((init.headers ?? {}) as Record<string, string>)['x-health-grant'] });
    if (url.includes('/api/health/twin')) return json(200, TWIN);
    if (url.includes('/api/health/grants')) return json(200, GRANTS);
    if (url.includes('/api/health/grant')) {
      return json(200, {
        grant: { ...TWIN.grants[0], id: 'grant-fresh999', agent: 'Dr. New' },
        holder: { token: MINTED, shownOnce: true, present: `x-health-grant: ${MINTED}`, note: 'This is the only time the secret exists outside the holder.' },
      });
    }
    return json(200, {});
  }));
});
afterEach(() => { clearHolderToken(); localStorage.clear(); vi.unstubAllGlobals(); });

describe('health twin · sharing panel under holder binding', () => {
  it('renders holderBound as a visible difference between the two grants', async () => {
    const w = mount(HealthTwin);
    await flush();

    const marks = w.findAll('.g-bound');
    expect(marks.length).toBe(2);
    expect(marks[0].classes()).toContain('bound');
    expect(marks[0].text()).toContain('holder-bound');
    expect(marks[1].classes()).toContain('unbound');
    expect(marks[1].text()).toContain('authenticates nobody');
    expect(marks[0].text()).not.toBe(marks[1].text());
  });

  it('disables "exercise this grant" for grants whose token this session does not hold', async () => {
    const w = mount(HealthTwin);
    await flush();

    const buttons = w.findAll('.g-actions button').filter((b) => b.text().includes('exercise'));
    expect(buttons.length).toBe(2);
    for (const b of buttons) expect(b.attributes('disabled')).toBeDefined();
    expect(buttons[0].attributes('title')).toContain('do not hold');
  });

  it('shows the minted token once, labels it unrecoverable, and never persists it', async () => {
    const w = mount(HealthTwin);
    await flush();

    await w.find('.sh-form input').setValue('Dr. New');
    await w.findAll('.sh-form button').find((b) => b.text().includes('Grant read'))!.trigger('click');
    await flush();

    const panel = w.find('.sh-issued');
    expect(panel.exists()).toBe(true);
    expect(panel.find('.iss-tok').text()).toBe(MINTED);
    expect(panel.text()).toContain('shown once');
    expect(panel.text()).toMatch(/not recoverable/);

    // it exists on screen, and nowhere else
    expect(JSON.stringify(localStorage)).not.toContain('mInTeD');
    expect(JSON.stringify(sessionStorage)).not.toContain('mInTeD');
    expect(document.cookie).not.toContain('mInTeD');
    // and no request ever carried it in a URL
    for (const c of calls) expect(c.url).not.toContain('mInTeD');
  });

  it('dismissing the minted token clears it from the surface', async () => {
    const w = mount(HealthTwin);
    await flush();
    await w.find('.sh-form input').setValue('Dr. New');
    await w.findAll('.sh-form button').find((b) => b.text().includes('Grant read'))!.trigger('click');
    await flush();

    expect(w.find('.sh-issued').exists()).toBe(true);
    await w.findAll('.iss-actions button').find((b) => b.text().includes('done'))!.trigger('click');
    await flush();
    expect(w.find('.sh-issued').exists()).toBe(false);
    expect(w.html()).not.toContain('mInTeD');
  });
});
