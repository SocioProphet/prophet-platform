// Reduce-based min/max. `Math.min(...arr)` / `Math.max(...arr)` spread the whole
// array as call arguments and throw `RangeError: Maximum call stack size exceeded`
// once the array is large enough (tens of thousands — reachable at H3 res-9 or on
// big OSM street responses). These iterate instead, so they never overflow.
// Semantics match Math.min/max on the empty array (Infinity / -Infinity).
export function minOf(arr: readonly number[]): number {
  let m = Infinity;
  for (const x of arr) if (x < m) m = x;
  return m;
}

export function maxOf(arr: readonly number[]): number {
  let m = -Infinity;
  for (const x of arr) if (x > m) m = x;
  return m;
}
