import { describe, it, expect, vi, afterEach } from 'vitest';
import { catalog, ApiError } from '../pages/studio/api';

// The catalog ops cockpit (#1361) is only as trustworthy as the client under it: an id that
// isn't encoded becomes a broken link or a path-injection into catalog-gateway, and a swallowed
// error paints an empty "healthy" cockpit over a dead backend. These pin both.

function fakeFetch(body: unknown, ok = true, status = 200) {
  const text = typeof body === 'string' ? body : JSON.stringify(body);
  return vi.spyOn(globalThis, 'fetch' as any).mockResolvedValue({
    ok, status, text: async () => text,
  } as any);
}

afterEach(() => vi.restoreAllMocks());

describe('studio catalog api client', () => {
  it('dcatUrl encodes the asset id (no unescaped slash/space/hash leaking into the path)', () => {
    expect(catalog.dcatUrl('a b/c?d#e')).toBe(
      '/svc/catalog/v1/catalog/asset/a%20b%2Fc%3Fd%23e.dcat.json',
    );
    // a plain id round-trips unchanged
    expect(catalog.dcatUrl('dataset-42')).toBe(
      '/svc/catalog/v1/catalog/asset/dataset-42.dcat.json',
    );
  });

  it('resolve()/lineage() hit catalog-gateway with the id percent-encoded', async () => {
    const spy = fakeFetch({ kind: 'dataset', entry: {} });
    await catalog.resolve('dataset', 'ns/a b');
    expect(spy).toHaveBeenLastCalledWith(
      '/svc/catalog/v1/catalog/dataset/ns%2Fa%20b',
      expect.anything(),
    );
    await catalog.lineage('asset', 'x/y');
    expect(spy).toHaveBeenLastCalledWith(
      '/svc/catalog/v1/catalog/asset/x%2Fy/lineage',
      expect.anything(),
    );
  });

  it('readout()/slo() hit the ops-plane endpoints and return the parsed body', async () => {
    fakeFetch({ schema_version: 'v0', slo_id: 's1', verdict: 'ok', objectives: [] });
    const slo = await catalog.slo();
    expect((globalThis.fetch as any)).toHaveBeenLastCalledWith(
      '/svc/catalog/v1/catalog/ops/slo',
      expect.anything(),
    );
    expect(slo.verdict).toBe('ok');
  });

  it('surfaces a backend failure as ApiError — never a silent empty cockpit', async () => {
    fakeFetch({ error: 'catalog-gateway unreachable' }, false, 503);
    await expect(catalog.readout()).rejects.toBeInstanceOf(ApiError);
    await expect(catalog.readout()).rejects.toMatchObject({ status: 503 });
  });
});
