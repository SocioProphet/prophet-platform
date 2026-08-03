class NonceStore {
  constructor() {
    this.seen = new Map();
  }

  consume(nonce, now) {
    if (typeof nonce !== 'string' || nonce.length < 8) {
      return { ok: false, reason: 'nonce.invalid' };
    }
    if (this.seen.has(nonce)) {
      return { ok: false, reason: 'nonce.reused', first_seen_at: this.seen.get(nonce) };
    }
    this.seen.set(nonce, now);
    return { ok: true, reason: 'nonce.consumed' };
  }

  has(nonce) {
    return this.seen.has(nonce);
  }

  size() {
    return this.seen.size;
  }
}

module.exports = { NonceStore };
