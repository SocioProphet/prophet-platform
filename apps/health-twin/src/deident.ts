// Wall 4 — de-identification. Produces a de-identified view of the twin so a clinician can be granted a
// BLINDED slice: they opine on the data, not the person. Approach = HIPAA Safe-Harbor-style identifier
// removal + consistent date-SHIFTING (a per-view offset that breaks absolute dates while PRESERVING
// intervals, which are clinically meaningful). Direct identifiers (name/label, provider names, free-text
// notes) are stripped; the subject becomes a stable pseudonym; clinical codes/values/units/tiers are
// preserved (that is exactly what the reviewer needs). Non-diagnostic; synthetic data only.

import { createHash, createHmac } from 'node:crypto';

// ── PSEUDONYM DERIVATION ────────────────────────────────────────────────────────────────────────
// The pseudonym was a 32-bit djb2 digest. Over PHI that is not a de-identification boundary: the
// entire 2^32 output space enumerates in seconds, and distinct subjects start colliding by the
// birthday bound at ~77k subjects — two people silently becoming one "anonymous" record.
//
// WHAT A WIDER DIGEST FIXES, AND WHAT IT DOES NOT — read this before trusting `anon:`.
// SHA-256 truncated to 128 bits closes the OUTPUT space: you cannot find a second input that maps
// to a given pseudonym, and you cannot enumerate the outputs. It does NOT close the INPUT space.
// `salt` defaults to the literal 'default', and server.ts calls deidentify(bundle()) with no salt
// at all, so on the default path the pseudonym is a pure function of a subject id. Subject ids are
// low-entropy and guessable, and an attacker re-identifying by guessing never needed to invert the
// hash — only to run it FORWARDS over candidate ids and compare. Against that attack a 256-bit
// digest is worth exactly as much as a 32-bit one.
//
// A KEY is the only thing that closes the input space, so the derivation is HMAC-SHA256 whenever
// HEALTH_TWIN_DEID_KEY is set: without the key the forward function cannot be computed at all, and
// guessing the subject id stops being enough.
//
// THE FALLBACK IS REAL AND IT IS NOT PROTECTED. There is no key management in this service to
// source a key from, so when the variable is unset the derivation falls back to unkeyed SHA-256,
// warns once on stderr, and — the part that matters — RECORDS THE FACT in the de-id receipt
// (`keyed: false`, `derivation: 'sha256'`). An unkeyed view is honestly labelled as unkeyed rather
// than presented as protected. Treat unkeyed pseudonyms as pseudonymous-but-guessable, never as
// anonymised, and do not release them outside a trust boundary that would also accept the raw ids.
const DEID_KEY_VAR = 'HEALTH_TWIN_DEID_KEY';
// read per call, not at import: a process may configure the key after this module loads, and the
// invariants exercise both the keyed and unkeyed branches in one run.
const deidKey = (): string => process.env[DEID_KEY_VAR] ?? '';

let warnedUnkeyed = false;
function warnIfUnkeyed(): void {
  if (deidKey() || warnedUnkeyed) return;
  warnedUnkeyed = true;
  console.warn(
    `[deident] ${DEID_KEY_VAR} is not set — pseudonyms are UNKEYED sha256. They are stable and ` +
    'collision-resistant, but anyone who can GUESS a subject id can recompute the pseudonym and ' +
    'confirm the guess. Receipts are marked keyed:false. Do not treat these views as anonymised.',
  );
}

// Domain-separated derivation. The pseudonym and the date shift come from the SAME subject id and
// salt, so they must not come from the same digest: sharing one would let anybody holding a
// pseudonym solve for that view's date shift and undo the shifting (and vice-versa). The domain
// tag is part of the hashed message, and the message is JSON-encoded so a '|' inside a subject id
// cannot be re-parsed as a field boundary.
function derive(domain: 'pseudonym' | 'dateshift', subjectId: string, salt: string): string {
  const msg = JSON.stringify([domain, subjectId, salt]);
  const key = deidKey();
  warnIfUnkeyed();
  return key
    ? createHmac('sha256', key).update(msg).digest('hex')
    : createHash('sha256').update(msg).digest('hex');
}

// 32 hex = 128 bits. The truncation is DELIBERATE, not an oversight: 128 bits is past any
// collision or enumeration concern for a subject population, while keeping the token short enough
// to appear in a UI, a URL and a reviewer's notes. The security limit on this value is the input
// space described above, not these 128 bits — lengthening it would buy nothing.
const PSEUDONYM_HEX = 32;

// Date shift in [-183, +182] days, from 64 bits of the dateshift-domain digest.
// BigInt, not parseInt: parseInt over a hex string longer than 13 digits silently exceeds 2^53 and
// returns a rounded float, so the low bits — the ones the modulus actually consumes — are lost and
// the "shift" degenerates toward a handful of values. BigInt is exact. Modulo bias over 2^64 into
// 366 buckets is ~1e-17 and irrelevant here.
function dateShiftFrom(digest: string): number {
  return Number(BigInt(`0x${digest.slice(0, 16)}`) % 366n) - 183;
}

const shiftDate = (iso: string, days: number): string => {
  if (!iso || iso.length < 7) return iso;
  const d = new Date(iso.length === 7 ? `${iso}-01` : iso);
  if (isNaN(d.getTime())) return iso;
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
};

export interface DeidReceipt {
  method: 'safe-harbor+date-shift';
  pseudonym: string;
  identifiersRemoved: string[]; // categories handled
  dateShiftDays: number;        // preserves intervals; absolute dates broken
  scope: DisclosureScope;       // the patient's agreed disclosure
  // How the pseudonym was actually derived on THIS view. A receipt that reported a protection the
  // run did not have would be worse than no receipt, so these are recorded from the live key state
  // rather than from intent: `keyed: false` means a guessable subject id yields this pseudonym.
  derivation: 'hmac-sha256' | 'sha256';
  keyed: boolean;
  at: string;
}

// Disclosure scope — set by the PATIENT'S agreement. 'standard' shares the clinical essentials a doctor
// needs (age-band + sex + facts) and nothing identifying. 'minimal' shares only the facts. Anything
// beyond 'standard' is a doctor request the patient must approve (see consult.requestMore).
export type DisclosureScope = 'minimal' | 'standard';

// The de-identified view a blinded reviewer sees. Note: NO name/label/provider, subject is a pseudonym.
export interface DeidView {
  subject: { pseudonym: string; ageBand?: string; sex?: string };
  systems: {
    id: string; label: string; organs: string[];
    observations: { code: string; codeSystem: string; display: string; value: number; unit: string; refLow?: number; refHigh?: number; effective: string; trend?: number[]; epistemic: string; organ?: string }[];
    conditions: { code: string; codeSystem: string; display: string; onset: string; clinicalStatus: string; epistemic: string; organ?: string }[];
    encounters: { type: string; date: string }[]; // provider + free-text note REMOVED
    imaging: { modality: string; bodySite: string; date: string; description: string; epistemic: string }[];
  }[];
  disclaimer: string;
  receipt: DeidReceipt;
}

const NONDX = 'De-identified record for blinded review. Not a diagnosis; a clinician forms an opinion. Synthetic data.';

// Build a de-identified view from the twin bundle. `salt` scopes the pseudonym + date-shift to a consult
// so different consults are unlinkable. `scope` = the patient's agreed disclosure ('standard' keeps the
// coarsened age-band + sex a doctor needs). The bundle is the shape returned by the engine's bundle().
export function deidentify(bundle: any, salt = 'default', scope: DisclosureScope = 'standard'): DeidView {
  const subjectId = bundle?.subject?.id ?? 'subject';
  // `anon:` prefix is load-bearing — INVARIANT 1 asserts the subject was reduced to a pseudonym by
  // testing for it. 32 hex of a domain-separated digest follows (see PSEUDONYM_HEX).
  const pseudonym = `anon:${derive('pseudonym', subjectId, salt).slice(0, PSEUDONYM_HEX)}`;
  // per-view deterministic date shift in [-183, +182] days — breaks absolute dates, preserves
  // intervals. Separate domain, so holding the pseudonym does not reveal the shift.
  const dateShiftDays = dateShiftFrom(derive('dateshift', subjectId, salt));
  const keyed = deidKey().length > 0;
  const removed = new Set<string>();

  const systems = (bundle?.systems ?? []).map((s: any) => ({
    id: s.id, label: s.label, organs: s.organs,
    observations: (s.observations ?? []).map((o: any) => ({
      code: o.code, codeSystem: o.codeSystem, display: o.display, value: o.value, unit: o.unit,
      refLow: o.refLow, refHigh: o.refHigh, effective: shiftDate(o.effective, dateShiftDays), trend: o.trend,
      epistemic: o.epistemic, organ: o.organ,
    })),
    conditions: (s.conditions ?? []).map((c: any) => ({
      code: c.code, codeSystem: c.codeSystem, display: c.display, onset: shiftDate(c.onset, dateShiftDays),
      clinicalStatus: c.clinicalStatus, epistemic: c.epistemic, organ: c.organ,
    })),
    encounters: (s.encounters ?? []).map((e: any) => {
      if (e.provider) removed.add('provider-names');
      if (e.note) removed.add('free-text-notes');
      return { type: e.type, date: shiftDate(e.date, dateShiftDays) }; // provider + note dropped
    }),
    imaging: (s.imaging ?? []).map((im: any) => ({
      modality: im.modality, bodySite: im.bodySite, date: shiftDate(im.date, dateShiftDays),
      description: im.description, epistemic: im.epistemic,
    })),
  }));

  if (bundle?.subject?.label) removed.add('names');
  if (bundle?.subject?.note) removed.add('narrative');
  removed.add('dates'); // shifted

  // 'standard' scope keeps the coarsened demographics a doctor needs; 'minimal' shares only facts.
  const subject: DeidView['subject'] = { pseudonym };
  if (scope === 'standard') {
    if (bundle?.subject?.ageBand) subject.ageBand = bundle.subject.ageBand;
    if (bundle?.subject?.sex) subject.sex = bundle.subject.sex;
  }
  return {
    subject,
    systems,
    disclaimer: NONDX,
    receipt: {
      method: 'safe-harbor+date-shift', pseudonym, identifiersRemoved: [...removed].sort(),
      dateShiftDays, scope,
      derivation: keyed ? 'hmac-sha256' : 'sha256', keyed,
      at: new Date().toISOString(),
    } as DeidReceipt,
  };
}

// Invariant helper: does a de-identified view leak any known direct identifier field? Used by the
// enforced non-diagnostic/de-id test. Returns the offending paths (empty = clean).
export function identifierLeaks(view: any): string[] {
  const leaks: string[] = [];
  const scan = (obj: any, path: string) => {
    if (obj == null || typeof obj !== 'object') return;
    for (const [k, v] of Object.entries(obj)) {
      const p = path ? `${path}.${k}` : k;
      // direct identifiers forbidden ANYWHERE in a de-identified view
      if (/^(name|note|provider|mrn|ssn|dob|email|phone|address|subjectLabel)$/i.test(k) && v) leaks.push(p);
      // `label`/`id` are PHI only on the subject (a system's anatomical label like "Cardiovascular" is not)
      if (/^(label|id)$/i.test(k) && v && /(^|\.)subject(\.|$)/i.test(p)) leaks.push(p);
      if (typeof v === 'object') scan(v, p);
    }
  };
  scan(view, '');
  return leaks;
}
