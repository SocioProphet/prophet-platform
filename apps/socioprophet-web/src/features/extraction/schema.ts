// Information-extraction schema — the entity types / classes / patterns / topics we
// care about, made first-class + editable. The extractor is a Holmes stand-in
// (deterministic, pattern-based); a real Holmes adapter (agent-machine) swaps in
// behind the same Extraction shape. Extracted entities feed the graph; claims feed
// Sherlock evidence search.

export type EntityClass = 'org' | 'person' | 'place' | 'money' | 'metric' | 'date' | 'law' | 'topic';

export interface EntityTypeDef { class: EntityClass; label: string; color: string }
export const ENTITY_TYPES: EntityTypeDef[] = [
  { class: 'org', label: 'Organization', color: '#e3b341' },
  { class: 'person', label: 'Person', color: '#4bbf73' },
  { class: 'place', label: 'Place', color: '#38bdf8' },
  { class: 'law', label: 'Law / rule', color: '#c58af9' },
  { class: 'money', label: 'Money', color: '#7ee2a8' },
  { class: 'metric', label: 'Metric', color: '#93b4ff' },
  { class: 'date', label: 'Date', color: '#f0a37e' },
  { class: 'topic', label: 'Topic', color: '#a3e635' },
];
export const entityColor = (c: EntityClass) => ENTITY_TYPES.find((t) => t.class === c)?.color ?? '#8b949e';

// Topic taxonomy — the "topics / vectors we care about" (Slashdot-style sections).
export const TOPIC_TAXONOMY: Record<string, string[]> = {
  'AI Governance': ['provenance', 'automated decision', 'model', 'ai', 'disclosure', 'audit'],
  'Markets': ['market', 'equities', 'yield', 'credit', 'commodities', 'issuance', 'spreads'],
  'Regulation': ['rule', 'comment period', 'framework', 'directive', 'adequacy', 'compliance'],
  'Supply & Energy': ['grid', 'interconnect', 'supply', 'logistics', 'corridor', 'energy'],
  'Data & Privacy': ['data', 'cross-border', 'transfer', 'privacy'],
  'Civic': ['humanitarian', 'housing', 'tenant', 'community', 'election'],
  'Technology': ['local-first', 'gitea', 'cloud-shell', 'retrieval', 'on-device'],
};

export interface ExtractedEntity { text: string; class: EntityClass; confidence: number }
export interface ExtractedClaim { text: string; confidence: number }
export interface Extraction { entities: ExtractedEntity[]; topics: string[]; claims: ExtractedClaim[] }

const STOP = new Set(['The', 'A', 'An', 'This', 'That', 'These', 'Those', 'It', 'They', 'We', 'In', 'On', 'For', 'And', 'But', 'Or', 'As', 'At', 'By', 'To', 'Of', 'Would', 'Recommends', 'Establishes', 'Sets']);
const LAW_MARK = /\b(Act|Rule|Bill|Directive|Guidance|Case|Framework|Regulation)\b/;
const ORG_MARK = /\b(Inc|Corp|LLC|Ltd|Commission|Committee|Agency|Department|Board|Group|Coalition|Society|Office|Tribunal|Bank|Exchange)\b/;

export function extract(text: string): Extraction {
  const entities: ExtractedEntity[] = [];
  const seen = new Set<string>();
  const add = (t: string, c: EntityClass, conf: number) => { const k = `${c}:${t.toLowerCase()}`; if (!seen.has(k) && t.trim().length > 1) { seen.add(k); entities.push({ text: t.trim(), class: c, confidence: conf }); } };

  for (const m of text.matchAll(/\$\s?[\d,][\d,.]*\s?(?:billion|million|trillion|bn|k|m|b)?/gi)) add(m[0].trim(), 'money', 0.95);
  for (const m of text.matchAll(/\b\d+(?:\.\d+)?\s?(?:%|percent|days?|months?|years?)\b/gi)) add(m[0].trim(), 'metric', 0.9);
  for (const m of text.matchAll(/\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}|\b(?:19|20)\d{2}\b/g)) add(m[0].trim(), 'date', 0.85);
  // Capitalized runs → law / org / person
  for (const m of text.matchAll(/\b([A-Z][a-zA-Z.]+(?:[ -][A-Z][a-zA-Z.]+){1,4})\b/g)) {
    const t = m[1]!;
    if (STOP.has(t.split(/[ -]/)[0]!)) continue;
    const cls: EntityClass = LAW_MARK.test(t) ? 'law' : ORG_MARK.test(t) ? 'org' : 'org';
    add(t, cls, 0.7);
  }

  const lc = text.toLowerCase();
  const topics = Object.entries(TOPIC_TAXONOMY).filter(([, kws]) => kws.some((k) => lc.includes(k))).map(([t]) => t);

  const claims: ExtractedClaim[] = [];
  for (const s of text.split(/(?<=[.!?])\s+/)) {
    if (/\b(would|shall|must|requires?|establishes?|prohibits?|mandates?|proposes?|recommends?|sets? a?)\b/i.test(s) && s.length > 25) {
      claims.push({ text: s.trim(), confidence: 0.75 });
    }
  }
  return { entities, topics, claims: claims.slice(0, 4) };
}
