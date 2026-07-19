import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchPeopleLive } from '../data/adapters/wikidataLive';

const search = { search: [{ id: 'Q42', label: 'Douglas Adams', description: 'English writer and humorist' }, { id: 'Q95', label: 'Google', description: 'American technology company' }] };
const details = {
  entities: {
    Q42: { claims: { P31: [{ mainsnak: { datavalue: { value: { id: 'Q5' } } } }], P2002: [{ mainsnak: { datavalue: { value: 'douglasadams' } } }], P856: [{ mainsnak: { datavalue: { value: 'https://douglasadams.com/' } } }] } },
    Q95: { claims: { P31: [{ mainsnak: { datavalue: { value: { id: 'Q4830453' } } } }] } }, // business → not Q5 → org
  },
};
afterEach(() => vi.restoreAllMocks());

describe('wikidata live People/OSINT adapter', () => {
  it('resolves people vs orgs and maps social claims to accounts/selectors', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(search) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(details) }));
    const r = await fetchPeopleLive('adams');
    expect(r).not.toBeNull();
    expect(r!).toHaveLength(2);
    const adams = r![0]!;
    expect(adams.id).toBe('wd-Q42');
    expect(adams.kind).toBe('person'); // P31 = Q5
    expect(adams.accounts.some((a) => a.platform === 'x' && a.handle === '@douglasadams')).toBe(true);
    expect(adams.selectors.some((s) => s.kind === 'domain' && s.value === 'douglasadams.com')).toBe(true);
    expect(adams.osint[0]!.name).toContain('Q42'); // QID as provenance
    expect(r![1]!.kind).toBe('org'); // not Q5
  });

  it('fails closed on search error / empty, and survives a details failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: () => Promise.resolve({}) }));
    expect(await fetchPeopleLive('x')).toBeNull();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ search: [] }) }));
    expect(await fetchPeopleLive('x')).toBeNull();
    // search ok, details throws → still returns entities (best-effort details)
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(search) })
      .mockRejectedValueOnce(new Error('offline')));
    const r = await fetchPeopleLive('adams');
    expect(r!).toHaveLength(2);
    expect(r![0]!.kind).toBe('org'); // no details → default (not Q5)
  });
});
