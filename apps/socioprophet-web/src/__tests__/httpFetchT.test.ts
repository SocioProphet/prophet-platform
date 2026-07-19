import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchT } from '../data/adapters/http';

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

describe('fetchT (fetch with timeout)', () => {
  it('aborts after `ms` when the request never resolves → rejects (AbortError)', async () => {
    vi.useFakeTimers();
    // fetch that only rejects when its signal aborts (models a stalled connection).
    vi.stubGlobal('fetch', (_url: string, init?: RequestInit) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
    }));
    const p = fetchT('https://x.test', {}, 50);
    const assertion = expect(p).rejects.toMatchObject({ name: 'AbortError' });
    await vi.advanceTimersByTimeAsync(60);
    await assertion;
  });

  it('resolves and clears the timer on a fast response (no dangling abort)', async () => {
    vi.useFakeTimers();
    const clearSpy = vi.spyOn(globalThis, 'clearTimeout');
    const body = new Response('ok', { status: 200 });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(body));
    const res = await fetchT('https://x.test', {}, 50);
    expect(res.status).toBe(200);
    expect(clearSpy).toHaveBeenCalled(); // finally{} cleared the abort timer
  });

  it('forwards caller init and attaches an abort signal', async () => {
    const spy = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', spy);
    await fetchT('https://x.test', { method: 'POST', headers: { accept: 'application/json' } }, 1000);
    const [, init] = spy.mock.calls[0]!;
    expect(init.method).toBe('POST');
    expect(init.headers).toEqual({ accept: 'application/json' });
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });
});
