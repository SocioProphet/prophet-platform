// The spinal correspondence chart — the chiropractic poster, done with THREE honestly-separated lenses.
// Same spinal level, three overlays, each carrying its epistemic tier (mirrors ontogenesis
// Domains/health-anatomy.ttl · https://socioprophet.md/ont/health#):
//   • modern       = evidence-based segmental/autonomic innervation           → VERIFIED
//   • chiropractic = the classic "meric" spinal-nerve → organ chart           → TRADITIONAL (attributed, not asserted)
//   • tcm          = proposed meridian/segmental bridge                        → HYPOTHESIS
// Non-diagnostic: this correlates and attributes; it never claims a subluxation causes a disease.
// `organ` (one of the twin's 9) links a correspondence to the person's records; `target` is the
// descriptive region for structures outside the twin's organ set.

export type Lens = 'modern' | 'chiropractic' | 'tcm';
export type Tier = 'verified' | 'traditional' | 'hypothesis';
export const LENS_TIER: Record<Lens, Tier> = { modern: 'verified', chiropractic: 'traditional', tcm: 'hypothesis' };
export const LENS_LABEL: Record<Lens, string> = { modern: 'Modern neuroanatomy', chiropractic: 'Chiropractic meric', tcm: 'TCM meridian' };
export const TIER_EPI: Record<Tier, string> = { verified: 'verified', traditional: 'attested', hypothesis: 'hypothesis' };

export interface Corr { lens: Lens; target: string; organ?: string }
export interface Seg { id: string; region: 'cervical' | 'thoracic' | 'lumbar' | 'sacral'; iri: string; corr: Corr[] }

const H = 'https://socioprophet.md/ont/health#';
const s = (id: string, region: Seg['region'], corr: Corr[]): Seg => ({ id, region, iri: H + id, corr });

export const SPINE: Seg[] = [
  s('C1', 'cervical', [{ lens: 'chiropractic', target: 'head, pituitary, inner ear', organ: 'Brain' }]),
  s('C2', 'cervical', [{ lens: 'chiropractic', target: 'eyes, optic/auditory nerve, sinuses', organ: 'Brain' }]),
  s('C3', 'cervical', [{ lens: 'modern', target: 'diaphragm (phrenic C3–C5)' }, { lens: 'chiropractic', target: 'cheeks, outer ear, face' }]),
  s('C4', 'cervical', [{ lens: 'modern', target: 'diaphragm (phrenic C3–C5)' }, { lens: 'chiropractic', target: 'nose, lips, eustachian tube' }]),
  s('C5', 'cervical', [{ lens: 'modern', target: 'diaphragm (phrenic C3–C5)' }, { lens: 'chiropractic', target: 'vocal cords, pharynx' }]),
  s('C6', 'cervical', [{ lens: 'chiropractic', target: 'neck muscles, shoulders, tonsils' }]),
  s('C7', 'cervical', [{ lens: 'chiropractic', target: 'thyroid, shoulder bursae, elbows' }]),
  s('T1', 'thoracic', [{ lens: 'modern', target: 'heart (cardiac sympathetic)', organ: 'Heart' }, { lens: 'chiropractic', target: 'arms, hands, esophagus, trachea' }]),
  s('T2', 'thoracic', [{ lens: 'modern', target: 'heart, coronary vessels', organ: 'Heart' }, { lens: 'chiropractic', target: 'heart, coronary arteries', organ: 'Heart' }]),
  s('T3', 'thoracic', [{ lens: 'modern', target: 'lungs, bronchi', organ: 'Lungs' }, { lens: 'chiropractic', target: 'lungs, bronchi, pleura, chest', organ: 'Lungs' }]),
  s('T4', 'thoracic', [{ lens: 'modern', target: 'lungs', organ: 'Lungs' }, { lens: 'chiropractic', target: 'gallbladder, common duct' }]),
  s('T5', 'thoracic', [{ lens: 'modern', target: 'stomach (sympathetic)', organ: 'Stomach' }, { lens: 'chiropractic', target: 'liver, solar plexus, blood', organ: 'Liver' }, { lens: 'tcm', target: 'Stomach / Liver meridian region', organ: 'Stomach' }]),
  s('T6', 'thoracic', [{ lens: 'modern', target: 'stomach', organ: 'Stomach' }, { lens: 'chiropractic', target: 'stomach', organ: 'Stomach' }]),
  s('T7', 'thoracic', [{ lens: 'modern', target: 'pancreas, duodenum', organ: 'Pancreas' }, { lens: 'chiropractic', target: 'pancreas, duodenum', organ: 'Pancreas' }]),
  s('T8', 'thoracic', [{ lens: 'modern', target: 'liver, spleen', organ: 'Liver' }, { lens: 'chiropractic', target: 'spleen' }]),
  s('T9', 'thoracic', [{ lens: 'modern', target: 'liver, adrenal glands', organ: 'Liver' }, { lens: 'chiropractic', target: 'adrenal glands' }]),
  s('T10', 'thoracic', [{ lens: 'modern', target: 'kidneys (sympathetic)', organ: 'Kidneys' }, { lens: 'chiropractic', target: 'kidneys', organ: 'Kidneys' }]),
  s('T11', 'thoracic', [{ lens: 'modern', target: 'kidneys, ureters', organ: 'Kidneys' }, { lens: 'chiropractic', target: 'kidneys, ureters', organ: 'Kidneys' }]),
  s('T12', 'thoracic', [{ lens: 'modern', target: 'small intestine', organ: 'Intestines' }, { lens: 'chiropractic', target: 'small intestine, lymph', organ: 'Intestines' }]),
  s('L1', 'lumbar', [{ lens: 'modern', target: 'large intestine', organ: 'Intestines' }, { lens: 'chiropractic', target: 'large intestine, inguinal rings', organ: 'Intestines' }]),
  s('L2', 'lumbar', [{ lens: 'chiropractic', target: 'appendix, abdomen, upper leg' }]),
  s('L3', 'lumbar', [{ lens: 'chiropractic', target: 'reproductive organs, bladder, knees', organ: 'Bladder' }, { lens: 'tcm', target: 'Kidney meridian region', organ: 'Kidneys' }]),
  s('L4', 'lumbar', [{ lens: 'chiropractic', target: 'lower back, sciatic nerve' }]),
  s('L5', 'lumbar', [{ lens: 'chiropractic', target: 'lower legs, ankles, feet' }]),
  s('S2', 'sacral', [{ lens: 'modern', target: 'bladder, bowel (parasympathetic S2–S4)', organ: 'Bladder' }]),
  s('S3', 'sacral', [{ lens: 'modern', target: 'bladder, reproductive (parasympathetic)', organ: 'Bladder' }]),
  s('S4', 'sacral', [{ lens: 'modern', target: 'bladder, bowel (parasympathetic)', organ: 'Bladder' }, { lens: 'chiropractic', target: 'sacrum, buttocks' }]),
];
