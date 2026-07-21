// Guideline-grounded reasoning — the reasoning-column attack that meets OpenEvidence/Med-PaLM on their
// turf, but sovereign + CITED + non-diagnostic. Reads the twin's own numbers (labs, vitals, conditions)
// and surfaces recommendations grounded in REAL clinical guidelines (ACC/AHA, ADA, USPSTF, KDIGO), each
// with its source, a strength, and a plain explanation. It NEVER diagnoses or prescribes — it says "here
// is what the guidelines say about your numbers; discuss with your clinician." Deterministic, local-first.
import { OBSERVATIONS, CONDITIONS, SUBJECT } from './data.js';

export interface Guidance {
  finding: string;         // the observation that triggered it (from the person's own record)
  says: string;            // what the guideline says, in plain words
  source: string;          // the real guideline it's grounded in
  strength: 'screen' | 'discuss' | 'monitor' | 'confirm';
  cites: string[];         // record ids this is grounded on
}

const obs = (code: string) => OBSERVATIONS.find((o) => o.code === code);
const hasCond = (code: string) => CONDITIONS.some((c) => c.code === code);
const ageNum = () => { const m = /(\d+)/.exec(String((SUBJECT as any).ageBand ?? '')); return m ? Number(m[1]) : undefined; };

// Each rule is grounded in a named guideline; thresholds are the guideline's own. Non-diagnostic framing
// is structural (strength = screen/discuss/monitor/confirm, never "diagnose").
export function guidance(): { subject: string; items: Guidance[]; disclaimer: string } {
  const items: Guidance[] = [];

  const ldl = obs('13457-7');
  if (ldl && ldl.value >= 100) {
    const high = ldl.value >= 190;
    items.push({
      finding: `LDL cholesterol ${ldl.value} ${ldl.unit} (target <100)`,
      says: high
        ? 'LDL ≥190 is a statin-benefit group on its own. A high-intensity statin discussion is warranted.'
        : `LDL is above target${hasCond('38341003') ? ', and with hypertension your 10-year cardiovascular risk is higher' : ''}. Guidelines suggest discussing lifestyle and statin candidacy (via an ASCVD risk estimate) with your clinician.`,
      source: 'ACC/AHA 2018 Blood Cholesterol Guideline',
      strength: 'discuss', cites: [ldl.id],
    });
  }

  const a1c = obs('4548-4');
  if (a1c) {
    if (a1c.value >= 5.7 && a1c.value < 6.5) items.push({
      finding: `HbA1c ${a1c.value}% (prediabetes range 5.7–6.4)`,
      says: 'This is the prediabetes range. Intensive lifestyle change (7% weight loss + activity) cuts progression to diabetes by ~58%; annual A1c monitoring is recommended.',
      source: 'ADA Standards of Care in Diabetes',
      strength: 'monitor', cites: [a1c.id],
    });
    else if (a1c.value >= 6.5) items.push({
      finding: `HbA1c ${a1c.value}% (≥6.5)`,
      says: 'This value is in the diabetes range. A single value does not confirm a diagnosis — your clinician confirms with a repeat or second test.',
      source: 'ADA Standards of Care in Diabetes',
      strength: 'confirm', cites: [a1c.id],
    });
  }

  const sbp = obs('8480-6');
  if (sbp) {
    if (sbp.value >= 140) items.push({ finding: `Systolic BP ${sbp.value} mmHg (stage 2, ≥140)`, says: 'This is stage-2 range. Guidelines recommend confirming with out-of-office readings and reviewing treatment with your clinician.', source: 'ACC/AHA 2017 High Blood Pressure Guideline', strength: 'confirm', cites: [sbp.id] });
    else if (sbp.value >= 130) items.push({ finding: `Systolic BP ${sbp.value} mmHg (stage 1, 130–139)`, says: 'This is stage-1 range. Guidelines recommend confirming readings and lifestyle change; medication depends on your overall cardiovascular risk.', source: 'ACC/AHA 2017 High Blood Pressure Guideline', strength: 'monitor', cites: [sbp.id] });
  }

  const egfr = obs('33914-3');
  if (egfr && egfr.value < 90) items.push({
    finding: `eGFR ${egfr.value} mL/min`,
    says: egfr.value < 60 ? 'Below 60 for ≥3 months would meet the CKD threshold. Confirm with a repeat eGFR + urine albumin.' : 'Mildly reduced. Worth periodic monitoring, especially alongside blood pressure.',
    source: 'KDIGO CKD Guideline', strength: egfr.value < 60 ? 'confirm' : 'monitor', cites: [egfr.id],
  });

  // age-based preventive screening (USPSTF) — grounded on the person's own age band
  const age = ageNum();
  if (age != null && age >= 45 && age <= 75) items.push({
    finding: `Age ${(SUBJECT as any).ageBand}`,
    says: 'Colorectal cancer screening is recommended for adults 45–75 (colonoscopy every 10 years, or a stool-based test on its schedule).',
    source: 'USPSTF Colorectal Cancer Screening', strength: 'screen', cites: [],
  });

  return {
    subject: SUBJECT.id,
    items,
    disclaimer: 'What clinical guidelines say about your own recorded numbers — informational, cited, and NOT a diagnosis or a prescription. Bring it to your clinician to decide together.',
  };
}
