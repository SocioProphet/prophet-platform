/**
 * BOOT SMOKE — the rejection ledger is scoped by the grant, at the HTTP surface.
 *
 * invariants.ts proves `rejectionLedger(limit, only)` filters correctly as a FUNCTION. That is not
 * the same claim as "the endpoint scopes". The leak this closes lived in the handler, not in the
 * ledger: `GET /api/health/dynamics/rejections` called `rejectionLedger(limit)` with no `only`, so a
 * clinician holding a cardiovascular-only grant — refused the renal forecast at /predict — could
 * read the renal trajectory out of the refusals instead. A port that moved the filter into gate.ts
 * but left the handler calling it unscoped would pass every unit invariant and still leak. So this
 * boots the real server and asks the real endpoint.
 *
 * The refusals are driven through the ORDINARY PUBLIC PATH: `covariates` is caller-supplied on
 * POST /predict, so an unprivileged request drives the surrogate across the admissibility bounds
 * and fills the ledger across all three compartments. Nothing test-only is reachable here — the
 * overrideDelta hook is deliberately not wired to the network — which is precisely why the ledger
 * is a real disclosure surface and not a debug artefact.
 *
 * TEETH BOTH WAYS. A scoping test that only asserts refusals is indistinguishable from an endpoint
 * that is simply broken, so the full-scope and no-grant reads must still return everything.
 *
 * Run: npx tsx src/dynamics/ledger-scope.smoke.ts
 */
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const PORT = Number(process.env.SMOKE_PORT ?? 8231);
const BASE = `http://127.0.0.1:${PORT}`;
const here = dirname(fileURLToPath(import.meta.url));
const serverEntry = resolve(here, '../server.ts');

let fails = 0;
const ok = (cond: boolean, label: string) => {
  console.log(`  ${cond ? '✓' : '✗'} ${label}`);
  if (!cond) fails++;
};

const j = async (path: string, init?: RequestInit) => {
  const res = await fetch(`${BASE}${path}`, init);
  let body: any = null;
  try { body = await res.json(); } catch { /* non-JSON is a body of null, status still asserted */ }
  return { status: res.status, body };
};

const grant = async (agent: string, scopeSpec: unknown) =>
  (await j('/api/health/grant', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ agent, scope: 'custom', scopeSpec }),
  })).body?.grant?.id as string;

const child = spawn('npx', ['tsx', serverEntry], {
  env: { ...process.env, PORT: String(PORT) },
  stdio: ['ignore', 'pipe', 'pipe'],
});
let serverLog = '';
child.stdout.on('data', (d) => { serverLog += d; });
child.stderr.on('data', (d) => { serverLog += d; });

const shutdown = () => { try { child.kill('SIGKILL'); } catch { /* already gone */ } };
process.on('exit', shutdown);

try {
  // wait for listen
  let up = false;
  for (let i = 0; i < 120 && !up; i++) {
    try { up = (await fetch(`${BASE}/healthz`)).ok; } catch { await new Promise((r) => setTimeout(r, 250)); }
  }
  if (!up) { console.error('server never came up:\n' + serverLog); shutdown(); process.exit(1); }

  console.log('\n▶ BOOT SMOKE — the rejection ledger is scoped by grant at the HTTP surface');

  // Fill the ledger across all three compartments through the public predict path.
  await j('/api/health/predict', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      horizonDays: 365, stepDays: 30,
      covariates: { adherencePdc: 0, reninIndex: 50, bmi: 90, uacr: 9000 },
    }),
  });

  // ── UNSCOPED (no grant): the operator view. Everything, as before. ────────────────────────────
  const all = await j('/api/health/dynamics/rejections');
  const organs = new Set<string>((all.body?.rejections ?? []).map((r: any) => r.compartment));
  ok(all.status === 200 && all.body.count > 0, `an ungranted read still returns the ledger (${all.body?.count} refusals)`);
  ok(organs.has('cardio') && organs.has('hepatic') && organs.has('renal'),
     `the unscoped ledger spans every compartment (${[...organs].sort().join(', ')})`);

  // ── CARDIOVASCULAR-ONLY GRANT: cardio entries only, totals recomputed. ────────────────────────
  const cardioGrant = await grant('dr-cardio', { systems: ['cardiovascular'], kinds: 'all', lookbackDays: null });
  const scoped = await j(`/api/health/dynamics/rejections?grant=${cardioGrant}`);
  const sBody = scoped.body ?? {};
  const sOrgans = new Set<string>((sBody.rejections ?? []).map((r: any) => r.compartment));
  ok(scoped.status === 200, 'a cardiovascular grant may read the ledger');
  ok(sOrgans.size === 1 && sOrgans.has('cardio'),
     `a cardiovascular-only grant sees ONLY cardiovascular refusals (${[...sOrgans].join(', ') || 'none'})`);
  ok(sBody.count === (sBody.rejections ?? []).length && sBody.count < all.body.count,
     `count is recomputed over the scoped set (${sBody.count}, not the whole-ledger ${all.body.count})`);
  ok(Object.values(sBody.byReason ?? {}).reduce((a: number, b: any) => a + b, 0) === sBody.count,
     'byReason sums to the scoped count — the histogram discloses no out-of-scope refusal');
  // the renal trajectory must not be reconstructable from anything in the response
  ok(!JSON.stringify(sBody.rejections ?? []).includes('renal') && !('renal' in (sBody.byReason ?? {})),
     'no renal value appears anywhere in the scoped response — the /predict refusal cannot be walked around');
  ok(Array.isArray(sBody.grant?.withheldSystems) && sBody.grant.withheldSystems.length > 0,
     `the response NAMES what was withheld rather than silently omitting it (${JSON.stringify(sBody.grant?.withheldSystems)})`);

  // ── A GRANT WITH NO COMPARTMENT IN SCOPE: 403, not an empty 200. ──────────────────────────────
  // An empty ledger and a refused read are different facts, and a 200 with count:0 would assert the
  // first while meaning the second — the caller would conclude the twin had refused nothing.
  const outOfScope = await grant('dr-derm', { systems: ['integumentary'], kinds: 'all', lookbackDays: null });
  const denied = await j(`/api/health/dynamics/rejections?grant=${outOfScope}`);
  ok(denied.status === 403, `a grant with no compartment in scope is refused 403 (got ${denied.status})`);
  ok(denied.body?.blocked === true && typeof denied.body?.reason === 'string',
     'the refusal is explicit and states a reason');
  ok(denied.body?.rejections === undefined && denied.body?.count === undefined,
     'the 403 carries no ledger content and no whole-ledger total');

  // ── AN UNKNOWN / REVOKED GRANT: 403 with a receipt. ───────────────────────────────────────────
  const bogus = await j('/api/health/dynamics/rejections?grant=grant-does-not-exist');
  ok(bogus.status === 403 && bogus.body?.receipt, 'an unknown grant is refused 403 and the refusal is receipted');

  // ── TEETH THE OTHER WAY — a full-scope grant still sees everything. ───────────────────────────
  const fullGrant = await grant('dr-full', { systems: 'all', kinds: 'all', lookbackDays: null });
  const fullRead = await j(`/api/health/dynamics/rejections?grant=${fullGrant}`);
  const fOrgans = new Set<string>((fullRead.body?.rejections ?? []).map((r: any) => r.compartment));
  ok(fullRead.status === 200 && fullRead.body.count === all.body.count,
     `a full-scope grant still sees the whole ledger (${fullRead.body?.count} of ${all.body.count})`);
  ok(fOrgans.has('cardio') && fOrgans.has('hepatic') && fOrgans.has('renal'),
     'a full-scope grant sees every compartment — the gate is scoping, not just refusing');

  console.log(`\n${fails === 0 ? '✓ THE REJECTION LEDGER IS GRANT-SCOPED AT THE ENDPOINT' : `✗ ${fails} scoped-ledger assertion(s) failed`}`);
} catch (e) {
  console.error('smoke failed:', e, '\n--- server log ---\n' + serverLog);
  fails++;
} finally {
  shutdown();
}
process.exit(fails === 0 ? 0 : 1);
