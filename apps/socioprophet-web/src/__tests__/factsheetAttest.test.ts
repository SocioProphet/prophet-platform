/**
 * Studio catalog "attested factsheet" receipt (Copilot #930).
 *
 * The bug this suite pins: the receipt used to hash only [id, connector, epistemic_mode,
 * columns.length, dir] while the rendered summary ALSO reports the dataset's name, its labels,
 * and the snapshot count (s.length). None of those three were in the hash, so two datasets whose
 * SUMMARIES genuinely differ — a different name, different labels, or a different snapshot count
 * with the same up/down direction — could mint the identical receipt. A receipt that doesn't cover
 * everything it attests isn't tamper-evident; it just looks like it is.
 */
import { describe, it, expect } from 'vitest';
import { attestFacts, attestReceipt, attestSummary } from '../pages/studio/factsheetAttest';
import type { Dataset } from '../services/studioApi';

function ds(over: Partial<Dataset> = {}): Dataset {
  return {
    id: 'proj-demo:ingest:people', name: 'people', labels: ['Person', 'Ingested'],
    connector: 'csv', epistemic_mode: 'observed', columns: ['id', 'name', 'age'],
    ...over,
  };
}

const SERIES = [10, 12, 14, 16]; // rising

describe('factsheet attestation receipt', () => {
  it('changes when the dataset NAME changes, even though everything the old receipt hashed stays the same', () => {
    const a = attestFacts(ds({ name: 'people' }), SERIES);
    const b = attestFacts(ds({ name: 'customers' }), SERIES);
    expect(a.summary).not.toBe(b.summary);          // the summary text really did change...
    expect(a.receipt).not.toBe(b.receipt);           // ...so the receipt must too
  });

  it('changes when the LABELS change', () => {
    const a = attestFacts(ds({ labels: ['Person'] }), SERIES);
    const b = attestFacts(ds({ labels: ['Person', 'VIP'] }), SERIES);
    expect(a.summary).not.toBe(b.summary);
    expect(a.receipt).not.toBe(b.receipt);
  });

  it('changes when the snapshot COUNT changes, even with the same direction', () => {
    const a = attestFacts(ds(), [10, 20]);           // rising, 2 snapshots
    const b = attestFacts(ds(), [10, 12, 14, 20]);    // rising, 4 snapshots
    expect(attestSummary(ds(), [10, 20])).not.toBe(attestSummary(ds(), [10, 12, 14, 20]));
    expect(a.receipt).not.toBe(b.receipt);
  });

  it('is stable and recomputable: same facts in, same receipt out', () => {
    const d = ds();
    expect(attestReceipt(d, SERIES)).toBe(attestReceipt(ds(), [...SERIES]));
  });

  it('is not fooled by a naive "|"-join: a part containing "|" cannot collide with its neighbour', () => {
    const a = attestFacts(ds({ name: 'a|b', labels: ['c'] }), SERIES);
    const b = attestFacts(ds({ name: 'a', labels: ['b|c'] }), SERIES);
    expect(a.receipt).not.toBe(b.receipt);
  });
});
