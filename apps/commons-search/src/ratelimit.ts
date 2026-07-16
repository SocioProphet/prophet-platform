/**
 * ratelimit.ts — per-author publish rate cap, to bound corpus-poisoning volume.
 *
 * A simple in-memory token bucket keyed by author pseudonym. In-memory is fine for Phase 1a: the cap is a coarse
 * abuse-brake, not an accounting system, and it degrades safely (a restart just refills buckets). Author keys are
 * held in a Map so a hostile pseudonym can't reach Object.prototype.
 */
export class RateLimiter {
  private buckets = new Map<string, { tokens: number; last: number }>()
  constructor(private ratePerMin: number, private burst: number) {}

  /** Returns true if the action is allowed (and consumes a token), false if the author is over their cap. */
  allow(author: string, now = Date.now()): boolean {
    const refillPerMs = this.ratePerMin / 60_000
    const b = this.buckets.get(author) ?? { tokens: this.burst, last: now }
    b.tokens = Math.min(this.burst, b.tokens + (now - b.last) * refillPerMs)
    b.last = now
    if (b.tokens < 1) { this.buckets.set(author, b); return false }
    b.tokens -= 1
    this.buckets.set(author, b)
    return true
  }
}
