// Reifier — lifts extraction output into Subject·Predicate·Object claims, each
// carrying its provenance tuple. A live Holmes/relation-extractor swaps in behind
// the same ReifiedClaim shape.
import { extract, type Extraction } from '../extraction/schema';
import type { ReifiedClaim } from './types';

const PREDICATES: Array<{ re: RegExp; p: string }> = [
  { re: /would require|requires?|must\b|shall\b|mandates?/i, p: 'requires' },
  { re: /establishes?|sets? (?:a |the |out )?/i, p: 'establishes' },
  { re: /prohibits?|bans?|restricts?/i, p: 'prohibits' },
  { re: /proposes?/i, p: 'proposes' },
  { re: /recommends?|advises?/i, p: 'recommends' },
  { re: /affects?|impacts?|hits?\b/i, p: 'affects' },
  { re: /cites?|references?/i, p: 'cites' },
  { re: /reopen(?:ed|s)?|permits?|allows?/i, p: 'permits' },
];

function hash(s: string): string { let h = 0; for (let i = 0; i < s.length; i += 1) h = (h * 31 + s.charCodeAt(i)) | 0; return (h >>> 0).toString(36); }

export function reify(text: string, source: string, extraction?: Extraction): ReifiedClaim[] {
  const ex = extraction ?? extract(text);
  const now = new Date().toISOString();
  const out: ReifiedClaim[] = [];
  const seen = new Set<string>();
  for (const claim of ex.claims) {
    const lc = claim.text.toLowerCase();
    const present = ex.entities
      .map((e) => ({ e, pos: lc.indexOf(e.text.toLowerCase()) }))
      .filter((x) => x.pos >= 0)
      .sort((a, b) => a.pos - b.pos);
    if (present.length === 0) continue;
    const subject = present[0]!.e.text;
    const object = present.length > 1 ? present[present.length - 1]!.e.text : (ex.topics[0] ?? 'the matter');
    if (subject === object) continue;
    const predicate = PREDICATES.find((p) => p.re.test(claim.text))?.p ?? 'concerns';
    const members = Array.from(new Set(present.map((x) => x.e.text)));
    const key = `${subject}|${predicate}|${object}`.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      id: `claim-${hash(key + source)}`,
      subject, predicate, object, members,
      provenance: { source, extractionMethod: 'Holmes pattern v0', modelVersion: 'holmes-fixture-0.1', timeObserved: now, confidence: claim.confidence },
      status: 'asserted', attestations: 0, disputes: [], topics: ex.topics,
    });
  }
  return out;
}
