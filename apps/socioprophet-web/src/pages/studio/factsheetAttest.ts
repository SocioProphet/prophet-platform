// The Studio catalog's "attested factsheet": a deterministic, recomputable summary built from a
// dataset's own facts, plus a content-id receipt meant to let a viewer verify the summary wasn't
// tampered with by recomputing the hash.
//
// Copilot #930: the receipt only hashed [id, connector, epistemic_mode, columns.length, dir] while
// the summary text ALSO reports d.name, d.labels and the snapshot count (s.length) — none of which
// were in the hash. Two datasets whose summaries genuinely differ (a different name, different
// labels, a different snapshot count with the same direction) could mint the IDENTICAL receipt,
// which defeats the point of a receipt: "recompute the hash to verify" only works if the hash
// actually covers everything being verified. Fixed by hashing every fact the summary reports, and
// JSON-encoding the parts (not '|'-joining them) so a value containing '|' can't collide with its
// neighbour either.
import type { Dataset } from '../../services/studioApi';

export function djb2(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) & 0xffffffff;
  return (h >>> 0).toString(16).padStart(8, '0');
}

export function seriesDirection(s: number[]): 'rising' | 'falling' | 'flat' {
  return s.length > 1 ? (s[s.length - 1] > s[0] ? 'rising' : s[s.length - 1] < s[0] ? 'falling' : 'flat') : 'flat';
}

export function attestSummary(d: Dataset, s: number[]): string {
  const dir = seriesDirection(s);
  return `${d.name} is a ${d.epistemic_mode} dataset${d.connector ? ` ingested via ${d.connector}` : ''} with ${d.columns.length} column${d.columns.length === 1 ? '' : 's'}${d.labels.length ? ` (${d.labels.join(', ')})` : ''}. Ingest volume is ${dir} across the ${s.length} most recent snapshots.`;
}

// Every fact the summary reports, in one JSON-encoded array — so the receipt actually covers what
// it attests. (id + epistemic_mode are included too, even though epistemic_mode alone is already in
// the summary text, so the receipt also binds identity, not just prose content.)
export function attestReceipt(d: Dataset, s: number[]): string {
  const dir = seriesDirection(s);
  const facts = [d.id, d.name, d.connector || '', d.epistemic_mode, d.columns.length, d.labels, dir, s.length];
  return `fs-${djb2(JSON.stringify(facts))}`;
}

export function attestFacts(d: Dataset, s: number[]): { summary: string; receipt: string } {
  return { summary: attestSummary(d, s), receipt: attestReceipt(d, s) };
}
