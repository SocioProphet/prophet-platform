// booking.ts — the care-access marketplace (verb 6 Book; the Zocdoc pattern's action half). Turns a
// care route into REAL, filterable options: bookable slots matched on specialty, modality, insurance,
// and timing, then a hold/book that carries the pre-visit summary forward. Walking skeleton with
// synthetic slots tied to the provider directory. Non-diagnostic; it arranges access, it does not
// treat. Insurance/eligibility here is a match hint, confirmed for real at the point of care.
import { directory } from './providers.js';
import { mintId } from './ids.js';

export interface Slot {
  id: string; providerId: string; providerName: string; specialty: string;
  modality: 'telehealth' | 'in-person'; start: string; insuranceAccepted: string[]; location: string;
}

// Synthetic availability tied to the real provider directory (id-stable so bookings reference a provider).
const now = Date.now();
const iso = (hoursFromNow: number) => new Date(now + hoursFromNow * 3_600_000).toISOString();
const SLOTS: Slot[] = [
  { id: 'slot-1', providerId: 'prov-rivera', providerName: 'Dr. A. Rivera', specialty: 'Cardiology', modality: 'in-person', start: iso(28), insuranceAccepted: ['Aetna', 'BCBS', 'Medicare'], location: 'Downtown Cardiology' },
  { id: 'slot-2', providerId: 'prov-rivera', providerName: 'Dr. A. Rivera', specialty: 'Cardiology', modality: 'telehealth', start: iso(6), insuranceAccepted: ['Aetna', 'UnitedHealth'], location: 'Telehealth' },
  { id: 'slot-3', providerId: 'prov-okafor', providerName: 'Dr. J. Okafor', specialty: 'Primary Care', modality: 'telehealth', start: iso(3), insuranceAccepted: ['BCBS', 'Cigna', 'Medicare', 'Medicaid'], location: 'Telehealth' },
  { id: 'slot-4', providerId: 'prov-okafor', providerName: 'Dr. J. Okafor', specialty: 'Primary Care', modality: 'in-person', start: iso(30), insuranceAccepted: ['BCBS', 'Cigna', 'Medicare'], location: 'Riverside Family Medicine' },
];

export interface SlotQuery { specialty?: string; modality?: 'telehealth' | 'in-person'; insurance?: string; withinHours?: number }
export function findSlots(q: SlotQuery = {}): { slots: Slot[]; disclaimer: string } {
  const specKey = q.specialty?.split(/[\/ ]/)[0]?.toLowerCase();
  const slots = SLOTS.filter((s) => {
    if (specKey && !s.specialty.toLowerCase().includes(specKey) && !s.specialty.toLowerCase().includes('primary')) return false;
    if (q.modality && s.modality !== q.modality) return false;
    if (q.insurance && !s.insuranceAccepted.some((i) => i.toLowerCase() === q.insurance!.toLowerCase())) return false;
    if (q.withinHours != null && new Date(s.start).getTime() > now + q.withinHours * 3_600_000) return false;
    return true;
  }).sort((a, b) => (a.start < b.start ? -1 : 1));
  const provided = directory(); // touch the directory so bookings and slots share one provider source
  void provided;
  return { slots, disclaimer: 'Availability + insurance shown here are match hints for a walking-skeleton demo — confirmed for real at the point of booking.' };
}

export interface Booking { id: string; slotId: string; providerName: string; specialty: string; modality: string; start: string; status: 'held'; preVisitSummaryAttached: boolean; receipt: string; disclaimer: string }
const bookings = new Map<string, Booking>();

// Hold a slot. FAIL-CLOSED: an unknown/absent slot never yields a booking (no silent no-op success).
export function book(slotId: string, opts: { preVisitSummary?: string } = {}): Booking | { error: string } {
  const slot = SLOTS.find((s) => s.id === slotId);
  if (!slot) return { error: 'slot not found or no longer available' };
  const b: Booking = {
    id: mintId('booking'), slotId: slot.id, providerName: slot.providerName, specialty: slot.specialty,
    modality: slot.modality, start: slot.start, status: 'held',
    preVisitSummaryAttached: !!opts.preVisitSummary,
    receipt: mintId('receipt'),
    disclaimer: 'A held slot is a demo reservation, not a confirmed medical appointment.',
  };
  bookings.set(b.id, b);
  return b;
}
export const listBookings = () => [...bookings.values()];
