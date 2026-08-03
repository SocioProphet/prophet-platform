const crypto = require('node:crypto');

function canonicalize(value) {
  if (value === null) return 'null';
  if (typeof value === 'string') return JSON.stringify(value.normalize('NFC'));
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new Error('non-finite number');
    return JSON.stringify(value);
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) return `[${value.map((item) => canonicalize(item)).join(',')}]`;
  if (typeof value === 'object') {
    const keys = Object.keys(value)
      .filter((key) => value[key] !== undefined)
      .sort();
    return `{${keys.map((key) => `${JSON.stringify(key)}:${canonicalize(value[key])}`).join(',')}}`;
  }
  throw new Error(`unsupported canonical value type: ${typeof value}`);
}

function sha256Hex(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function hmacSha256Hex(key, value) {
  return crypto.createHmac('sha256', key).update(value).digest('hex');
}

function stableHash(value) {
  return sha256Hex(canonicalize(value));
}

module.exports = {
  canonicalize,
  hmacSha256Hex,
  sha256Hex,
  stableHash
};
