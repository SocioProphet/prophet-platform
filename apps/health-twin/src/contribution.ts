// contribution.ts — the data cooperative (verb 10 Learn; the Segmed pattern). A patient may opt a
// DE-IDENTIFIED slice of their twin into a governed research/eval program under EXPLICIT consent,
// with a TRANSPARENT compensation record, REVOCABLE at any time. The doc's non-negotiable: "a patient
// should never be tricked into monetizing their data — explicit, revocable, understandable, and
// compensated fairly if value is created." Consent fails CLOSED (no agreement → no contribution), and
// what leaves is the de-identified view (identifierLeaks == 0), never raw PHI. Non-diagnostic.
import { deidentify, identifierLeaks } from './deident.js';
import { mintId } from './ids.js';

export interface ContributionProgram {
  id: string; name: string; purpose: string; dataScope: string;
  compensationModel: string; unitReward: number; governance: string;
}
const PROGRAMS: ContributionProgram[] = [
  { id: 'cardio-eval', name: 'Cardiometabolic model evaluation', purpose: 'benchmark triage + risk models on de-identified cardiometabolic records', dataScope: 'de-identified observations + conditions (no identifiers, date-shifted)', compensationModel: 'per-accepted-record', unitReward: 5, governance: 'IRB-style review; approved partners only; revocable' },
  { id: 'guideline-audit', name: 'Guideline-concordance audit', purpose: 'measure real-world concordance with published guidelines', dataScope: 'de-identified conditions + medications', compensationModel: 'flat participation credit', unitReward: 10, governance: 'internal quality program; revocable' },
];
export const programs = () => ({ programs: PROGRAMS, disclaimer: 'Participation is optional, explicit, and revocable. Only de-identified data leaves; you are compensated if value is created.' });

export interface Contribution {
  id: string; programId: string; program: string;
  consented: true; consentReceipt: string; deidReceipt: string;
  identifiersRemoved: string[]; leakCheck: 'clean' | 'blocked';
  compensation: { model: string; amount: number; currency: 'credit'; status: 'accrued' };
  revocable: true; revoked: boolean; joinedAt: string;
}
const contributions = new Map<string, Contribution>();

// Join a program. FAIL-CLOSED on consent (agreed !== true → refused). The slice is de-identified and
// re-checked for leaks; if any identifier survived, the contribution is BLOCKED rather than shipped.
export function contribute(programId: string, bundle: any, agreed: boolean): Contribution | { error: string } {
  const program = PROGRAMS.find((p) => p.id === programId);
  if (!program) return { error: 'program not found' };
  if (agreed !== true) return { error: 'explicit consent required — contribution refused (fail-closed)' };

  const view = deidentify(bundle, `contrib|${programId}`, 'minimal');
  const leaks = identifierLeaks(view);
  if (leaks.length) return { error: `de-identification incomplete (${leaks.join(', ')}) — contribution blocked` };

  const c: Contribution = {
    id: mintId('contribution'), programId, program: program.name,
    consented: true, consentReceipt: mintId('receipt'), deidReceipt: (view as any).receipt?.id ?? mintId('receipt'),
    identifiersRemoved: (view as any).receipt?.identifiersRemoved ?? [], leakCheck: 'clean',
    compensation: { model: program.compensationModel, amount: program.unitReward, currency: 'credit', status: 'accrued' },
    revocable: true, revoked: false, joinedAt: new Date().toISOString(),
  };
  contributions.set(c.id, c);
  return c;
}

export function revokeContribution(id: string): { revoked: boolean; reason?: string } {
  const c = contributions.get(id);
  if (!c) return { revoked: false, reason: 'contribution not found' };
  c.revoked = true;
  return { revoked: true };
}

// The compensation ledger — transparent by construction: every accrual, and what's still active.
export function ledger() {
  const all = [...contributions.values()];
  const active = all.filter((c) => !c.revoked);
  return {
    contributions: all.map((c) => ({ id: c.id, program: c.program, amount: c.compensation.amount, currency: c.compensation.currency, revoked: c.revoked, joinedAt: c.joinedAt })),
    totalAccrued: active.reduce((n, c) => n + c.compensation.amount, 0),
    currency: 'credit',
    disclaimer: 'Transparent compensation ledger. Amounts are demo credits; only de-identified data was contributed, and any entry can be revoked.',
  };
}
