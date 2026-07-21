// Apple Health connector. HealthKit has NO server API — data is read on-device (an iOS app queries
// HKQuantityType/HKCategoryType with per-type permission) and exported. So the live transport is an
// on-device export; the fixture below is shaped exactly like HealthKit samples (real
// HKQuantityTypeIdentifier keys, startDate/endDate/value/unit/sourceName/device). normalize() maps
// each sample → a LOINC-coded Vital-Signs Observation. Wearable-measured ⇒ epistemic 'observed'.
import type { Connector, IngestResult, IngestMode } from '../ingest.js';
import { emptyResult, provenance, routeLoinc } from '../ingest.js';

// real HealthKit sample shape (what an on-device export yields)
interface HKSample { type: string; value: number; unit: string; startDate: string; endDate: string; sourceName: string; device?: string }

// HKQuantityTypeIdentifier → { LOINC, display }
const HK_LOINC: Record<string, { code: string; display: string; refLow?: number; refHigh?: number }> = {
  HKQuantityTypeIdentifierHeartRate: { code: '8867-4', display: 'Heart rate', refLow: 60, refHigh: 100 },
  HKQuantityTypeIdentifierRestingHeartRate: { code: '40443-4', display: 'Resting heart rate', refLow: 50, refHigh: 90 },
  HKQuantityTypeIdentifierHeartRateVariabilitySDNN: { code: '80404-7', display: 'Heart rate variability (SDNN)' },
  HKQuantityTypeIdentifierOxygenSaturation: { code: '59408-5', display: 'Oxygen saturation (SpO2)', refLow: 95, refHigh: 100 },
  HKQuantityTypeIdentifierBloodPressureSystolic: { code: '8480-6', display: 'Systolic blood pressure', refLow: 90, refHigh: 120 },
  HKQuantityTypeIdentifierBloodPressureDiastolic: { code: '8462-4', display: 'Diastolic blood pressure', refLow: 60, refHigh: 80 },
  HKQuantityTypeIdentifierVO2Max: { code: '80404-7', display: 'VO2 max (cardio fitness)' },
  HKQuantityTypeIdentifierStepCount: { code: '55423-8', display: 'Step count' },
  HKQuantityTypeIdentifierBodyMass: { code: '29463-7', display: 'Body weight' },
};

// clearly-synthetic fixture — matches the real HealthKit export shape, no real PHI.
const FIXTURE: HKSample[] = [
  { type: 'HKQuantityTypeIdentifierRestingHeartRate', value: 62, unit: 'count/min', startDate: '2026-07-19T07:02:00Z', endDate: '2026-07-19T07:02:00Z', sourceName: 'Apple Watch', device: 'Watch7,1' },
  { type: 'HKQuantityTypeIdentifierHeartRateVariabilitySDNN', value: 48, unit: 'ms', startDate: '2026-07-19T07:02:00Z', endDate: '2026-07-19T07:02:00Z', sourceName: 'Apple Watch', device: 'Watch7,1' },
  { type: 'HKQuantityTypeIdentifierOxygenSaturation', value: 97, unit: '%', startDate: '2026-07-19T03:14:00Z', endDate: '2026-07-19T03:14:00Z', sourceName: 'Apple Watch', device: 'Watch7,1' },
  { type: 'HKQuantityTypeIdentifierVO2Max', value: 41.2, unit: 'mL/min·kg', startDate: '2026-07-15T18:20:00Z', endDate: '2026-07-15T18:20:00Z', sourceName: 'Apple Watch', device: 'Watch7,1' },
  { type: 'HKQuantityTypeIdentifierStepCount', value: 8421, unit: 'count', startDate: '2026-07-19T00:00:00Z', endDate: '2026-07-19T23:59:59Z', sourceName: 'iPhone', device: 'iPhone16,1' },
  { type: 'HKQuantityTypeIdentifierBloodPressureSystolic', value: 134, unit: 'mmHg', startDate: '2026-07-18T08:30:00Z', endDate: '2026-07-18T08:30:00Z', sourceName: 'Withings BPM', device: 'BPM-Connect' },
  { type: 'HKQuantityTypeIdentifierBloodPressureDiastolic', value: 85, unit: 'mmHg', startDate: '2026-07-18T08:30:00Z', endDate: '2026-07-18T08:30:00Z', sourceName: 'Withings BPM', device: 'BPM-Connect' },
];

export const appleHealth: Connector = {
  id: 'apple-health', name: 'Apple Health (HealthKit)', kind: 'wearable',
  authModel: 'healthkit-on-device', sourceShape: 'HealthKit HKQuantitySample',
  uscdiClasses: ['Vital Signs'], modes: ['fixture', 'live'],
  async fetch(mode: IngestMode) {
    // live: read from an on-device HealthKit export (native bridge). fixture: the real-shaped samples.
    if (mode === 'fixture') return FIXTURE;
    throw new Error('apple-health live mode requires an on-device HealthKit export bridge');
  },
  normalize(raw: unknown, mode: IngestMode): IngestResult {
    const out: IngestResult = emptyResult();
    const samples = (raw as HKSample[]) ?? [];
    const prov = provenance(this, mode, this.sourceShape, 'Vital Signs');
    for (const s of samples) {
      const m = HK_LOINC[s.type];
      if (!m) continue;
      const { system, organ } = routeLoinc(m.code);
      out.observations.push({
        id: `ah-${s.type}-${s.startDate}`.replace(/[^\w-]/g, '').toLowerCase(),
        system, organ, code: m.code, codeSystem: 'LOINC', display: m.display,
        value: s.value, unit: s.unit, refLow: m.refLow, refHigh: m.refHigh,
        effective: s.startDate.slice(0, 10), epistemic: 'observed', provenance: { ...prov },
      });
    }
    return out;
  },
};
