// Easy data entry — the key to the doctor chart. A device reading, a spoken phrase, or a typed line
// ("BP 138/85, HR 72, glucose 110") becomes coded vital/lab observations, using the value-extracting
// clinical coder. Same path whether it comes from a Bluetooth cuff, a voice note, or the keyboard.
// tier = observed (device/self-entered); a clinician can later attest. Non-diagnostic.
import { codeText } from './clinical.js';
import { routeLoinc } from './ingest.js';

export interface Reading {
  id: string; system: string; organ: string; code: string; codeSystem: 'LOINC'; display: string;
  value: number; unit: string; effective: string; epistemic: 'observed'; by: string; source: string;
}

// LOINC → { unit, display } for the codes the coder emits (vitals + common labs)
const META: Record<string, { unit: string; display: string }> = {
  '85354-9': { unit: 'mmHg', display: 'Blood pressure' }, '8480-6': { unit: 'mmHg', display: 'Systolic blood pressure' }, '8462-4': { unit: 'mmHg', display: 'Diastolic blood pressure' },
  '8867-4': { unit: '/min', display: 'Heart rate' }, '59408-5': { unit: '%', display: 'Oxygen saturation' },
  '29463-7': { unit: 'kg', display: 'Body weight' }, '39156-5': { unit: 'kg/m2', display: 'Body mass index' },
  '2345-7': { unit: 'mg/dL', display: 'Glucose' }, '4548-4': { unit: '%', display: 'Hemoglobin A1c' },
  '13457-7': { unit: 'mg/dL', display: 'LDL cholesterol' }, '2085-9': { unit: 'mg/dL', display: 'HDL cholesterol' },
  '2571-8': { unit: 'mg/dL', display: 'Triglycerides' }, '2160-0': { unit: 'mg/dL', display: 'Creatinine' },
  '33914-3': { unit: 'mL/min', display: 'eGFR' }, '1742-6': { unit: 'U/L', display: 'ALT' },
};

function mk(code: string, value: number, by: string, source: string): Reading {
  const m = META[code] ?? { unit: '', display: code };
  const { system, organ } = routeLoinc(code);
  return { id: `rd-${code}-${Date.now()}-${Math.round(value)}`, system, organ, code, codeSystem: 'LOINC', display: m.display, value, unit: m.unit, effective: new Date().toISOString().slice(0, 10), epistemic: 'observed', by, source };
}

// Parse readings from free text/voice/device. Blood pressure "138/85" splits into systolic + diastolic.
export function parseReadings(text: string, by = 'patient', source = 'manual'): Reading[] {
  const out: Reading[] = [];
  for (const e of codeText(text).entities) {
    if ((e.category !== 'vital' && e.category !== 'lab') || !e.value || e.negated) continue;
    if (e.code === '85354-9' && e.value.includes('/')) {
      const [sys, dia] = e.value.split('/').map((n) => parseFloat(n));
      if (!isNaN(sys!)) out.push(mk('8480-6', sys!, by, source));
      if (!isNaN(dia!)) out.push(mk('8462-4', dia!, by, source));
    } else {
      const v = parseFloat(e.value);
      if (!isNaN(v)) out.push(mk(e.code, v, by, source));
    }
  }
  return out;
}
