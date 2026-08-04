// identity.ts — the PATIENT identity plane. The vision doc flags that "no patient identity plane
// exists here" — consent is issued by whoever operates the node. This closes that gap: a real person
// ENROLLS, receives a one-time patient credential, and thereafter authenticates as the OWNER of their
// twin. It's the third distinct actor, cleanly separated from the two the grant layer already has:
//   • operator (HEALTH_TWIN_TOKEN) — runs the node, may issue consent
//   • grant holder (x-health-grant) — a clinician a patient granted scoped, time-boxed access
//   • PATIENT (x-health-patient, here) — the person who OWNS the record and grants that access
// Reuses the proven grantauth holder-secret crypto (mint→digest→present a token; the secret is shown
// ONCE and never stored, so a stolen registry authenticates nobody). Fail-closed. Non-diagnostic.
import { createHash, randomBytes, timingSafeEqual } from 'node:crypto';
import { mintId } from './ids.js';

export const PATIENT_HEADER = 'x-health-patient';

function mintPatientSecret(): string { return randomBytes(32).toString('base64url'); }
function patientDigest(secret: string): string { return `sha256-${createHash('sha256').update(secret, 'utf8').digest('hex')}`; }
function digestEquals(a: string, b: string): boolean {
  const ad = createHash('sha256').update(a, 'utf8').digest();
  const bd = createHash('sha256').update(b, 'utf8').digest();
  return timingSafeEqual(ad, bd);
}
// split on the LAST dot: ids are dash/hex, base64url secrets carry - and _ but never a dot
export function parsePatientToken(raw: string): { patientId: string; secret: string } | null {
  const s = (raw ?? '').trim(); const i = s.lastIndexOf('.');
  if (i <= 0 || i === s.length - 1) return null;
  return { patientId: s.slice(0, i), secret: s.slice(i + 1) };
}

interface PatientRecord { id: string; displayName: string; enrolledAt: string; holderDigest: string; twinSubject: string | null; revoked: boolean }
const patients = new Map<string, PatientRecord>();

export interface EnrollResult {
  patient: { id: string; displayName: string; enrolledAt: string };
  credential: { token: string; header: string; present: string; shownOnce: true; note: string };
  receipt: string;
}

// Enroll a patient → mint a one-time credential. The secret is returned here and NOWHERE else.
export function enrollPatient(displayName = 'Patient', twinSubject: string | null = null): EnrollResult {
  const id = mintId('patient');
  const secret = mintPatientSecret();
  const rec: PatientRecord = { id, displayName: displayName.trim() || 'Patient', enrolledAt: new Date().toISOString(), holderDigest: patientDigest(secret), twinSubject, revoked: false };
  patients.set(id, rec);
  const token = `${id}.${secret}`;
  return {
    patient: { id, displayName: rec.displayName, enrolledAt: rec.enrolledAt },
    credential: {
      token, header: PATIENT_HEADER, present: `${PATIENT_HEADER}: ${token}`, shownOnce: true,
      note: 'This is the only time your patient credential exists outside your control. It is not recoverable — store it safely. The id alone is not a credential.',
    },
    receipt: mintId('receipt'),
  };
}

export type PatientAuth =
  | { ok: true; patientId: string; displayName: string }
  | { ok: false; reason: string };

// Authenticate as a patient from the presented credential. FAIL-CLOSED: a missing/malformed token, a
// bare id (no secret), an unknown id, a revoked patient, or a wrong secret all deny. The patient id is
// NOT a credential — presenting it without the secret is refused, both ways.
export function authenticatePatient(headers: Record<string, string | string[] | undefined>): PatientAuth {
  const raw = headers[PATIENT_HEADER];
  const value = Array.isArray(raw) ? raw[0] ?? '' : raw ?? '';
  const parsed = parsePatientToken(String(value));
  if (!parsed) return { ok: false, reason: `patient credential required — present ${PATIENT_HEADER}: <patient-id>.<secret>` };
  const rec = patients.get(parsed.patientId);
  if (!rec) return { ok: false, reason: 'unknown patient' };
  if (rec.revoked) return { ok: false, reason: 'patient credential revoked' };
  if (!digestEquals(patientDigest(parsed.secret), rec.holderDigest)) return { ok: false, reason: 'patient authentication failed' };
  return { ok: true, patientId: rec.id, displayName: rec.displayName };
}

// The patient's own profile (never the holder digest). Only the authenticated patient sees it.
export function patientProfile(patientId: string) {
  const rec = patients.get(patientId);
  if (!rec) return null;
  return { id: rec.id, displayName: rec.displayName, enrolledAt: rec.enrolledAt, twinSubject: rec.twinSubject, revoked: rec.revoked };
}

export function revokePatient(patientId: string): { revoked: boolean; reason?: string } {
  const rec = patients.get(patientId);
  if (!rec) return { revoked: false, reason: 'unknown patient' };
  rec.revoked = true;
  return { revoked: true };
}

export const patientCount = () => patients.size;
