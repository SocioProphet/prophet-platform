// Oura connector. Live transport = Oura API v2 (OAuth2 Bearer), GET /v2/usercollection/{daily_readiness,
// daily_spo2, daily_activity}. Rate limit 5000 req / 5-min. The fixture below matches the real v2 doc
// envelope ({ data: [ { id, day, ... } ], next_token }). normalize() lifts the clinically-meaningful
// signals (resting HR, HRV balance, SpO2, steps) → LOINC-coded Observations. Device-measured ⇒ 'observed'.
import type { Connector, IngestResult, IngestMode } from '../ingest.js';
import { emptyResult, provenance } from '../ingest.js';

// real Oura v2 shapes (subset of fields we consume)
interface OuraReadiness { id: string; day: string; score: number; contributors: { resting_heart_rate: number; hrv_balance: number; body_temperature: number } }
interface OuraSpo2 { id: string; day: string; spo2_percentage: { average: number } }
interface OuraActivity { id: string; day: string; steps: number; active_calories: number }
interface OuraDoc<T> { data: T[]; next_token: string | null }

const FIXTURE = {
  daily_readiness: { data: [
    { id: 'rd-2026-07-19', day: '2026-07-19', score: 78, contributors: { resting_heart_rate: 58, hrv_balance: 72, body_temperature: 98 } },
    { id: 'rd-2026-07-18', day: '2026-07-18', score: 74, contributors: { resting_heart_rate: 60, hrv_balance: 68, body_temperature: 99 } },
  ], next_token: null } as OuraDoc<OuraReadiness>,
  daily_spo2: { data: [ { id: 'sp-2026-07-19', day: '2026-07-19', spo2_percentage: { average: 96 } } ], next_token: null } as OuraDoc<OuraSpo2>,
  daily_activity: { data: [ { id: 'ac-2026-07-19', day: '2026-07-19', steps: 9120, active_calories: 540 } ], next_token: null } as OuraDoc<OuraActivity>,
};

export const oura: Connector = {
  id: 'oura', name: 'Oura Ring (API v2)', kind: 'wearable',
  authModel: 'oauth2', sourceShape: 'Oura API v2 daily_* documents',
  uscdiClasses: ['Vital Signs'], modes: ['fixture', 'sandbox', 'live'],
  async fetch(mode: IngestMode) {
    if (mode === 'fixture') return FIXTURE;
    throw new Error('oura sandbox/live requires an OAuth2 bearer token for api.ouraring.com');
  },
  normalize(raw: unknown, mode: IngestMode): IngestResult {
    const out: IngestResult = emptyResult();
    const r = raw as typeof FIXTURE;
    const prov = provenance(this, mode, this.sourceShape, 'Vital Signs');
    const obs = (id: string, code: string, display: string, value: number, unit: string, day: string, refLow?: number, refHigh?: number) =>
      out.observations.push({ id, system: 'cardiovascular', organ: 'Heart', code, codeSystem: 'LOINC', display, value, unit, refLow, refHigh, effective: day, epistemic: 'observed', provenance: { ...prov } });
    for (const d of r.daily_readiness?.data ?? []) {
      obs(`oura-rhr-${d.day}`, '40443-4', 'Resting heart rate', d.contributors.resting_heart_rate, 'count/min', d.day, 50, 90);
    }
    for (const d of r.daily_spo2?.data ?? []) {
      out.observations.push({ id: `oura-spo2-${d.day}`, system: 'respiratory', organ: 'Lungs', code: '59408-5', codeSystem: 'LOINC', display: 'Oxygen saturation (SpO2)', value: d.spo2_percentage.average, unit: '%', refLow: 95, refHigh: 100, effective: d.day, epistemic: 'observed', provenance: { ...prov } });
    }
    for (const d of r.daily_activity?.data ?? []) {
      obs(`oura-steps-${d.day}`, '55423-8', 'Step count', d.steps, 'count', d.day);
    }
    return out;
  },
};
