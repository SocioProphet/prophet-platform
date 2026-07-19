import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchFederalRegister } from '../data/adapters/federalRegisterLive';

const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
afterEach(() => vi.restoreAllMocks());

describe('federalRegisterLive', () => {
  it('maps real Federal Register docs into Dockets with real citation + url', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ results: [
      { title: 'Safety Standard for X', document_number: '2026-12345', publication_date: '2026-07-01', abstract: 'A rule about X.', html_url: 'https://www.federalregister.gov/d/2026-12345', type: 'Rule', agencies: [{ name: 'EPA' }] },
      { title: 'Proposed Rule Y', document_number: '2026-67890', publication_date: '2026-07-02', abstract: 'Proposes Y.', html_url: 'https://www.federalregister.gov/d/2026-67890', type: 'Proposed Rule', agencies: [{ name: 'DOT' }] },
      { title: 'no docnum', abstract: 'x' }, // dropped
    ] })));
    const r = await fetchFederalRegister();
    expect(r).toHaveLength(2);
    expect(r![0]).toMatchObject({ cite: '2026-12345', agency: 'EPA', status: 'enacted', jurisdiction: 'Federal', url: 'https://www.federalregister.gov/d/2026-12345' });
    expect(r![1].status).toBe('comment'); // proposed rule → open comment window
    expect(r![0].provenanceHash).toBe(''); // no fake hash — real source link instead
  });

  it('fails closed on empty, non-200, and throw', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ results: [] })));
    expect(await fetchFederalRegister()).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('', { status: 500 }))));
    expect(await fetchFederalRegister()).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('net'))));
    expect(await fetchFederalRegister()).toBeNull();
  });
});
