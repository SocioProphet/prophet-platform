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

// A key shorter than this is NOT a key for this purpose, and is refused rather than used.
// The key exists to close the INPUT space — to make the forward function incomputable to someone
// guessing subject ids. A one-character or whitespace key does not do that: it is enumerated as
// fast as the subject ids are. Accepting it would still stamp `keyed: true` / `hmac-sha256` on the
// receipt, and a reader who trusts that flag would be told the view is protected when it is not.
// The receipt's single job is to never overstate, so a degenerate key is rejected and the run falls
// back to the honest unkeyed path — labelled unkeyed, exactly like a missing key.
// 16 bytes = 128 bits, matching the pseudonym width; below that the flag would outrun the fact.
const MIN_DEID_KEY_BYTES = 16;

// read per call, not at import: a process may configure the key after this module loads, and the
// invariants exercise both the keyed and unkeyed branches in one run.
const rawDeidKey = (): string => process.env[DEID_KEY_VAR] ?? '';

/**
 * The EFFECTIVE key state for this call — one source of truth for both the derivation and the
 * receipt. These were two independent reads of the environment, which meant the receipt reported
 * what the environment said rather than what the derivation did; they agree today only because
 * nothing can interleave between them. Deriving both from one value makes the receipt structurally
 * unable to describe a derivation that did not happen.
 */
function keyState(): { key: string; keyed: boolean; rejected: boolean } {
  const raw = rawDeidKey();
  if (!raw) return { key: '', keyed: false, rejected: false };
  if (Buffer.byteLength(raw, 'utf8') < MIN_DEID_KEY_BYTES) return { key: '', keyed: false, rejected: true };
  return { key: raw, keyed: true, rejected: false };
}

let warnedUnkeyed = false;
let warnedRejected = false;
function warnIfUnkeyed(): void {
  const st = keyState();
  if (st.keyed) return;
  // A configured-but-refused key is a DIFFERENT operator situation from an unset one: somebody
  // intended protection and did not get it, so it must not be reported with the same message an
  // untouched deployment gets.
  if (st.rejected) {
    if (warnedRejected) return;
    warnedRejected = true;
    console.warn(
      `[deident] ${DEID_KEY_VAR} is set but is shorter than the ${MIN_DEID_KEY_BYTES}-byte minimum — ` +
      'it has been REFUSED, not used. A key this short does not close the guessing attack the key ' +
      'exists to close, and using it would let the receipt claim keyed:true for a protection you do ' +
      'not have. Falling back to UNKEYED sha256; receipts are marked keyed:false.',
    );
    return;
  }
  if (warnedUnkeyed) return;
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
  const { key, keyed } = keyState();
  warnIfUnkeyed();
  return keyed
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

// ── DATE SHIFTING ───────────────────────────────────────────────────────────────────────────────
// shiftDate used to FAIL OPEN. Anything it could not parse — a bare '2024', an empty string,
// 'not-a-date', a malformed-but-meaningful '2024-13-45' — was returned UNCHANGED, so an UNSHIFTED
// date survived into a view whose receipt claims 'safe-harbor+date-shift'. Today's synthetic data
// is all well-formed ISO, so nothing reaches those paths; the connector plane (Epic / CMS Blue
// Button / DICOMweb) lands date fields with no such guarantee. The failure is silent by
// construction: a passed-through date is byte-indistinguishable from a shifted one.
//
// Every date field now lands in exactly ONE of four outcomes, each explicit and each COUNTED on the
// receipt (see DeidReceipt.dates). The four are separated deliberately, because the old code got
// the bare-year case RIGHT — but by accident, through the very same `length < 7` short-circuit that
// waved the garbage through. Correct-by-accident and wrong are the same line of code until you
// split them apart.
//
// WHY A SENTINEL AND NOT A DROP. Dropping an unparseable date fails closed on the DATA but fails
// OPEN on the READER: an absent field is indistinguishable from "this subject had no such date", so
// the suppression becomes invisible at the point of use. That is the same silent-gap failure being
// fixed here, merely relocated from the writer to the reader. The sentinel makes the gap legible
// where it is READ; the receipt count makes it legible in the AUDIT RECORD.
export const DATE_UNSHIFTABLE = 'date-unshiftable';

// What a single date field became. Exactly one per field, and all four are counted.
export type DateOutcome = 'shifted' | 'yearOnly' | 'absent' | 'unshiftable';

export interface DateShiftCounts {
  shifted: number;      // parsed and moved by dateShiftDays
  yearOnly: number;     // bare 'YYYY' — deliberately passed through, see below
  absent: number;       // no date to shift ('' / null / undefined)
  unshiftable: number;  // replaced with DATE_UNSHIFTABLE — the receipt must not hide these
}

// The value shape shiftDateField can return. Copilot round-2 on the platform twin
// (SocioProphet/prophet-platform#1095) flagged the same defect here: the previous
// signature said `{ value: string }` but the absent branch preserved the original null /
// undefined so `undefined` fields stayed undefined rather than becoming '' — the type
// was lying by cast, and a caller that trusted it would deref `.length` on null. The
// three outcomes that DO carry a string still say so via the discriminated union.
export type ShiftDateResult =
  | { value: string; outcome: 'shifted' | 'yearOnly' | 'unshiftable' }
  | { value: null | undefined | ''; outcome: 'absent' };

const BARE_YEAR = /^\d{4}$/;
// The leading calendar date of an ISO-8601 value: 'YYYY-MM', 'YYYY-MM-DD', or 'YYYY-MM-DD' followed
// by a time. Matching the DATE and ignoring any time-of-day is what keeps this timezone-stable for
// offset-bearing and offset-less datetimes alike (see the UTC note below).
const ISO_LEAD = /^(\d{4})-(\d{2})(?:-(\d{2}))?(?:[T ].*)?$/;
const MS_PER_DAY = 86_400_000;
const SHIFTED_FORM = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Shift one date field, reporting WHICH of the four branches it took so the caller can count it.
 *
 * The arithmetic is UTC-only, and that is load-bearing. The previous implementation parsed with
 * `new Date(iso)` — which reads a date-only ISO string as UTC MIDNIGHT — then advanced it with
 * LOCAL-time `getDate`/`setDate`. Those two cancel only while the local UTC offset is identical on
 * both sides of the shift. Across a DST transition they do not, and the shipped code was measurably
 * NOT timezone-stable: under America/Los_Angeles, '2024-01-15' shifted +88d produced 2024-04-11,
 * where UTC, Asia/Kolkata and Pacific/Kiritimati (neither of the latter observes DST) all produced
 * 2024-04-12. The error is per-DATE, not per-view, so it also broke the one property this module
 * exists to preserve: the real 152-day interval 2024-01-15 → 2024-06-15 came back as 153 days under
 * LA, because only the earlier endpoint crossed the March transition. Whole days added to a UTC
 * instant cannot drift — there is no local offset left to fail to cancel.
 */
function shiftDateField(value: unknown, days: number): ShiftDateResult {
  // (3) ABSENT — there was no date. Not an error, and not something to stamp a sentinel onto.
  // Preserve the original value so an undefined field stays undefined rather than becoming ''
  // — but say so honestly in the return type. Dropping the `as string` cast means a caller
  // can no longer read `.length` on the returned value without narrowing first (the caller
  // in deidentify() reads `.value` only on the string-carrying branches; the absent branch
  // is discarded via `dates[r.outcome]++`).
  if (value === null || value === undefined || value === '') {
    return { value: value as null | undefined | '', outcome: 'absent' };
  }
  // A non-string in a date field is not a date. Fail closed rather than coerce it.
  if (typeof value !== 'string') return { value: DATE_UNSHIFTABLE, outcome: 'unshiftable' };

  // (2) BARE YEAR — an EXPLICIT ALLOW, not a fallthrough. HIPAA Safe Harbor permits year
  // granularity for dates (it is dates more precise than a year that must go), so 'YYYY' is already
  // de-identified and passing it through unshifted is correct. It is counted separately so that
  // "we allowed this" is never confused with "we failed to parse this".
  if (BARE_YEAR.test(value)) return { value, outcome: 'yearOnly' };

  // (1) WELL-FORMED — 'YYYY-MM' (treated as the 1st), 'YYYY-MM-DD', or either followed by a time.
  const m = ISO_LEAD.exec(value);
  if (m) {
    const year = Number(m[1]);
    const month = Number(m[2]);
    const day = m[3] === undefined ? 1 : Number(m[3]);
    // setUTCFullYear rather than Date.UTC(): Date.UTC maps a 2-digit year onto 19xx, which would
    // silently relocate a year like '0024'.
    const base = new Date(0);
    base.setUTCFullYear(year, month - 1, day);
    // Date normalises out-of-range parts instead of rejecting them — '2024-13-45' would quietly
    // become 2025-02-14. Round-tripping the components is what actually rejects a malformed date.
    if (
      base.getUTCFullYear() === year && base.getUTCMonth() === month - 1 && base.getUTCDate() === day
    ) {
      const shifted = new Date(base.getTime() + days * MS_PER_DAY).toISOString().slice(0, 10);
      // A year outside the 4-digit range formats as '+010000-…' and would emit a truncated string;
      // anything that is not a plain YYYY-MM-DD is treated as unshiftable rather than shipped.
      if (SHIFTED_FORM.test(shifted)) return { value: shifted, outcome: 'shifted' };
    }
  }

  // (4) EVERYTHING ELSE — unparseable. Replaced with the sentinel, never returned as itself.
  return { value: DATE_UNSHIFTABLE, outcome: 'unshiftable' };
}

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
  // What actually happened to every date field in THIS view, by branch. `method` says
  // 'safe-harbor+date-shift'; a receipt that made that claim while N dates went through unshifted
  // would be a receipt that lies, in exactly the way `keyed:false` above exists to prevent. A
  // non-zero `unshiftable` is the receipt declining to overstate: those fields carry
  // DATE_UNSHIFTABLE, not a date. `yearOnly` is a permitted pass-through, not a failure.
  dates: DateShiftCounts;
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
  // the SAME predicate derive() just used — not a second look at the environment
  const keyed = keyState().keyed;
  const removed = new Set<string>();
  // Per-view tally. Every shiftDate() call below lands in exactly one bucket, and the whole tally
  // goes on the receipt, so the count cannot drift from what was actually emitted.
  const dates: DateShiftCounts = { shifted: 0, yearOnly: 0, absent: 0, unshiftable: 0 };
  const shiftDate = (value: unknown): string | null | undefined => {
    const r = shiftDateField(value, dateShiftDays);
    dates[r.outcome]++;
    return r.value;
  };

  const systems = (bundle?.systems ?? []).map((s: any) => ({
    id: s.id, label: s.label, organs: s.organs,
    observations: (s.observations ?? []).map((o: any) => ({
      code: o.code, codeSystem: o.codeSystem, display: o.display, value: o.value, unit: o.unit,
      refLow: o.refLow, refHigh: o.refHigh, effective: shiftDate(o.effective), trend: o.trend,
      epistemic: o.epistemic, organ: o.organ,
    })),
    conditions: (s.conditions ?? []).map((c: any) => ({
      code: c.code, codeSystem: c.codeSystem, display: c.display, onset: shiftDate(c.onset),
      clinicalStatus: c.clinicalStatus, epistemic: c.epistemic, organ: c.organ,
    })),
    encounters: (s.encounters ?? []).map((e: any) => {
      if (e.provider) removed.add('provider-names');
      if (e.note) removed.add('free-text-notes');
      return { type: e.type, date: shiftDate(e.date) }; // provider + note dropped
    }),
    imaging: (s.imaging ?? []).map((im: any) => ({
      modality: im.modality, bodySite: im.bodySite, date: shiftDate(im.date),
      description: im.description, epistemic: im.epistemic,
    })),
  }));

  if (bundle?.subject?.label) removed.add('names');
  if (bundle?.subject?.note) removed.add('narrative');
  removed.add('dates'); // shifted — per-branch outcome is on receipt.dates, which does not round up

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
      dates,
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
