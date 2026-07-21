// CMS Blue Button 2.0 connector. Live transport = the CMS FHIR API (OAuth2, authorized at Medicare.gov)
// giving ~60M beneficiaries their Part A/B/D CLAIMS as FHIR ExplanationOfBenefit + Coverage + Patient,
// weekly-refreshed, up to 4 years back. Claims give the complete-across-providers view (esp. Part D
// medication FILLS = adherence signal) that clinical feeds miss. The fixture matches Blue Button EOB
// shape (type coding 'PDE' = Part D drug event, item.productOrService RxNorm). Claims-sourced ⇒ 'derived'.
import type { Connector, IngestResult, IngestMode } from '../ingest.js';
import { emptyResult, provenance } from '../ingest.js';

interface Coding { system?: string; code?: string; display?: string }
interface EOB {
  resourceType: 'ExplanationOfBenefit'; id: string;
  type: { coding: Coding[] }; billablePeriod?: { start: string };
  item?: { productOrService: { coding: Coding[] }; quantity?: { value: number }; servicedDate?: string }[];
}
interface CoverageR { resourceType: 'Coverage'; id: string; status: string; type?: { coding: Coding[] }; payor?: { display: string }[]; period?: { start: string; end?: string } }
interface Bundle { resourceType: 'Bundle'; type: string; entry?: { resource: EOB | CoverageR }[] }

const FIXTURE: Bundle = { resourceType: 'Bundle', type: 'searchset', entry: [
  { resource: { resourceType: 'Coverage', id: 'cov1', status: 'active', type: { coding: [{ system: 'https://bluebutton.cms.gov/resources/variables/mco_prd_type', code: 'PartD', display: 'Medicare Part D' }] }, payor: [{ display: 'CMS Medicare' }], period: { start: '2025-01-01', end: '2025-12-31' } } },
  { resource: { resourceType: 'ExplanationOfBenefit', id: 'pde1', type: { coding: [{ system: 'https://bluebutton.cms.gov/resources/codesystem/eob-type', code: 'PDE', display: 'Part D drug event' }] }, item: [{ productOrService: { coding: [{ system: 'http://www.nlm.nih.gov/research/umls/rxnorm', code: '314076', display: 'Lisinopril 10 MG Oral Tablet' }] }, quantity: { value: 90 }, servicedDate: '2026-06-12' }] } },
  { resource: { resourceType: 'ExplanationOfBenefit', id: 'pde2', type: { coding: [{ code: 'PDE', display: 'Part D drug event' }] }, item: [{ productOrService: { coding: [{ system: 'http://www.nlm.nih.gov/research/umls/rxnorm', code: '860975', display: 'Metformin 500 MG Oral Tablet' }] }, quantity: { value: 60 }, servicedDate: '2026-06-12' }] } },
] };

export const cmsBlueButton: Connector = {
  id: 'cms-blue-button', name: 'CMS Blue Button 2.0 (Medicare claims)', kind: 'claims',
  authModel: 'oauth2', sourceShape: 'FHIR ExplanationOfBenefit + Coverage',
  uscdiClasses: ['Medications', 'Health Insurance Information'], modes: ['fixture', 'sandbox', 'live'],
  async fetch(mode: IngestMode) {
    // sandbox: bluebutton.cms.gov synthetic beneficiaries; live: production w/ beneficiary OAuth grant.
    if (mode === 'fixture') return FIXTURE;
    throw new Error('cms-blue-button sandbox/live requires a Blue Button 2.0 OAuth token');
  },
  normalize(raw: unknown, mode: IngestMode): IngestResult {
    const out: IngestResult = emptyResult();
    const b = raw as Bundle;
    for (const e of b.entry ?? []) {
      const r = e.resource;
      if (r.resourceType === 'Coverage') {
        out.coverage.push({ id: `bb-cov-${r.id}`, payer: r.payor?.[0]?.display ?? 'CMS Medicare', kind: r.type?.coding?.[0]?.display ?? 'Medicare', status: r.status, period: `${r.period?.start ?? ''}${r.period?.end ? '–' + r.period.end : ''}`, epistemic: 'attested', provenance: provenance(this, mode, `${this.sourceShape} (Coverage)`, 'Health Insurance Information') });
      } else if (r.resourceType === 'ExplanationOfBenefit' && r.type.coding.some((c) => c.code === 'PDE')) {
        for (const it of r.item ?? []) {
          const c = it.productOrService.coding[0];
          out.medications.push({ id: `bb-fill-${r.id}`, system: 'hepatic', organ: 'Pancreas', code: c?.code ?? '', codeSystem: 'RxNorm', display: `${c?.display ?? 'medication'} — fill${it.quantity ? ` ×${it.quantity.value}` : ''}`, status: 'dispensed', effective: it.servicedDate ?? r.billablePeriod?.start ?? '', epistemic: 'derived', provenance: provenance(this, mode, `${this.sourceShape} (EOB Part D fill)`, 'Medications') });
        }
      }
    }
    return out;
  },
};
