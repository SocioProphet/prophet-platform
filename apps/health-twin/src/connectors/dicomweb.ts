// DICOMweb connector. Live transport = QIDO-RS (Query by ID for DICOM Objects over HTTP/JSON) against
// a DICOMweb server — study/series discovery in plain JSON, no legacy PACS/DIMSE. The fixture matches
// the real QIDO-RS response: an array of study objects keyed by DICOM tag ('0020000D' StudyInstanceUID,
// '00080060' Modality, '00081030' StudyDescription, '00080020' StudyDate, '00180015' BodyPartExamined),
// each value an { vr, Value } object. normalize() maps a study → an ImagingStudy. Imaging ⇒ 'attested'.
import type { Connector, IngestResult, IngestMode } from '../ingest.js';
import { emptyResult, provenance } from '../ingest.js';

// real QIDO-RS tag-keyed shape
type Tag = { vr: string; Value?: (string | number)[] };
type QidoStudy = Record<string, Tag>;

const val = (s: QidoStudy, tag: string): string => String(s[tag]?.Value?.[0] ?? '');
// DICOM BodyPartExamined → our anatomical system
const BODYPART_SYSTEM: Record<string, string> = { BRAIN: 'nervous', HEAD: 'nervous', CHEST: 'respiratory', LUNG: 'respiratory', HEART: 'cardiovascular', ABDOMEN: 'hepatic', KIDNEY: 'urinary' };

const FIXTURE: QidoStudy[] = [
  { '0020000D': { vr: 'UI', Value: ['1.2.840.113619.2.55.3.1'] }, '00080060': { vr: 'CS', Value: ['MR'] }, '00081030': { vr: 'LO', Value: ['MRI BRAIN W/O CONTRAST'] }, '00080020': { vr: 'DA', Value: ['20260520'] }, '00180015': { vr: 'CS', Value: ['BRAIN'] } },
  { '0020000D': { vr: 'UI', Value: ['1.2.840.113619.2.55.3.2'] }, '00080060': { vr: 'CS', Value: ['CR'] }, '00081030': { vr: 'LO', Value: ['CHEST PA AND LATERAL'] }, '00080020': { vr: 'DA', Value: ['20250914'] }, '00180015': { vr: 'CS', Value: ['CHEST'] } },
];

const fmtDate = (d: string) => (d.length === 8 ? `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}` : d);

export const dicomweb: Connector = {
  id: 'dicomweb', name: 'DICOMweb (QIDO-RS imaging)', kind: 'imaging',
  authModel: 'dicomweb-qido', sourceShape: 'DICOMweb QIDO-RS study metadata',
  uscdiClasses: ['Diagnostic Imaging'], modes: ['fixture', 'sandbox', 'live'],
  async fetch(mode: IngestMode) {
    // live/sandbox: GET {dicomwebBase}/studies (QIDO-RS) with bearer/basic auth → tag-keyed JSON.
    if (mode === 'fixture') return FIXTURE;
    throw new Error('dicomweb sandbox/live requires a DICOMweb QIDO-RS base URL + credentials');
  },
  normalize(raw: unknown, mode: IngestMode): IngestResult {
    const out: IngestResult = emptyResult();
    const studies = (raw as QidoStudy[]) ?? [];
    for (const s of studies) {
      const bodyPart = val(s, '00180015').toUpperCase();
      const system = BODYPART_SYSTEM[bodyPart] ?? 'nervous';
      out.imaging.push({
        id: `dcm-${val(s, '0020000D').replace(/\./g, '-')}`, system,
        modality: val(s, '00080060'), bodySite: val(s, '00180015') || bodyPart,
        date: fmtDate(val(s, '00080020')), description: val(s, '00081030'),
        epistemic: 'attested', provenance: provenance(this, mode, this.sourceShape, 'Diagnostic Imaging'),
      } as any);
    }
    return out;
  },
};
