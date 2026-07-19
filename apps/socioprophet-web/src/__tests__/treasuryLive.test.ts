import { describe, it, expect, vi, afterEach } from 'vitest';
import { _parseTreasuryXml, fetchTreasuryLive } from '../data/adapters/treasuryLive';

// Two dated entries mirroring the real Treasury Daily Par Yield Curve XML shape.
const XML = `<?xml version="1.0"?><feed>
<entry><content><m:properties>
  <d:NEW_DATE m:type="Edm.DateTime">2026-07-07T00:00:00</d:NEW_DATE>
  <d:BC_2YEAR m:type="Edm.Double">4.19</d:BC_2YEAR>
  <d:BC_10YEAR m:type="Edm.Double">4.55</d:BC_10YEAR>
  <d:BC_30YEAR m:type="Edm.Double">5.05</d:BC_30YEAR>
</m:properties></content></entry>
<entry><content><m:properties>
  <d:NEW_DATE m:type="Edm.DateTime">2026-07-08T00:00:00</d:NEW_DATE>
  <d:BC_2YEAR m:type="Edm.Double">4.21</d:BC_2YEAR>
  <d:BC_10YEAR m:type="Edm.Double">4.56</d:BC_10YEAR>
  <d:BC_30YEAR m:type="Edm.Double">5.06</d:BC_30YEAR>
</m:properties></content></entry>
</feed>`;

afterEach(() => vi.restoreAllMocks());

describe('treasury par yield parsing', () => {
  it('maps latest per-tenor yields onto US2Y/US10Y/US30Y with real values', () => {
    const q = _parseTreasuryXml(XML)!;
    expect(q.get('US2Y')!.price).toBe(4.21);
    expect(q.get('US10Y')!.price).toBe(4.56);
    expect(q.get('US30Y')!.price).toBe(5.06);
    expect(q.get('US10Y')!.asOf).toBe('2026-07-08');
  });

  it('computes day-over-day % change from the two latest dated entries', () => {
    const q = _parseTreasuryXml(XML)!;
    // (4.56 - 4.55) / 4.55 * 100 = 0.22
    expect(q.get('US10Y')!.changePct).toBe(0.22);
    expect(q.get('US2Y')!.changePct).toBeCloseTo(0.48, 2);
  });

  it('returns null for empty/dataless XML (fails closed)', () => {
    expect(_parseTreasuryXml('<feed></feed>')).toBeNull();
  });

  it('takes latest/prior by real date, not document order (feed reordering is safe)', () => {
    // Same two entries, emitted newest-first — must still pick 07-08 as latest.
    const reordered = XML.split('<entry').filter((c) => c.includes('NEW_DATE')).reverse().map((c) => '<entry' + c).join('');
    const q = _parseTreasuryXml('<feed>' + reordered + '</feed>')!;
    expect(q.get('US10Y')!.asOf).toBe('2026-07-08');
    expect(q.get('US10Y')!.changePct).toBe(0.22); // still (4.56-4.55)/4.55, not inverted
  });
});

describe('fetchTreasuryLive', () => {
  it('returns quotes on a healthy response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve(XML) }));
    const q = await fetchTreasuryLive();
    expect(q!.get('US2Y')!.price).toBe(4.21);
  });

  it('fails closed to null when the feed errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')));
    expect(await fetchTreasuryLive()).toBeNull();
  });
});
