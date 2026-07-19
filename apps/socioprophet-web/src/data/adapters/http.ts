// fetch with a hard timeout. Bare fetch() has no client-side deadline: if a
// connection stalls (Overpass under load is the classic case) the promise never
// resolves, the adapter's catch never fires, and the surface's liveState sticks
// on 'loading' forever — the "Go live" button then goes permanently dead. This
// aborts after `ms`, which surfaces as an AbortError → the adapter's existing
// catch → returns null → the surface falls back to fixture and shows 'error'.
export async function fetchT(input: RequestInfo | URL, init: RequestInit = {}, ms = 8000): Promise<Response> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(input, { ...init, signal: ctrl.signal });
  } finally {
    clearTimeout(timer);
  }
}
