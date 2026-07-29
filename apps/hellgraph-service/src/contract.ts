/**
 * contract — the vendored sourceos-spec membrane contract: schemas + hermetic validation.
 *
 * Schema provenance (vendored so validation needs no network and no spec checkout —
 * the same discipline as apps/market-replay/src/market_replay/contract.py):
 *     repo    SourceOS-Linux/sourceos-spec  (trading/effect families merged in PR #204)
 *     commit  7d74db818a943f2070285c2fc16e22f975d1b8d0  (origin/main, 2026-07-29;
 *             schema bytes identical to the #204 feature commit 487e4b61)
 *     files   schemas/EffectRequest.json     sha256 99829aa50b0ebb7d663072028c37e3a29cf4cb6d2fbbbe5d6af0dda979264084
 *             schemas/EffectDecision.json    sha256 29b7c4d9ce07b033b18f22382c3160e4eae9b56444a30cdf69b0c7a7c108d9e1
 *             schemas/OrderIntent.json       sha256 40ff7f8a47dd4288e343aacc74c62e24b092111d5a19d3c692d88e315235f6ce
 *             schemas/ExecutionReport.json   sha256 3eef1c1ce0e4b2bcbe0fb6f9419c0e65773f50c6b9c3e69b459f979c96ac91e1
 * Re-vendor by copying the files byte-identical from sourceos-spec and updating this
 * block. Each sha256 is asserted at import: a drifted or hand-edited copy fails LOUDLY
 * at startup, never silently at decide time — the membrane's whole claim is "what enters
 * the graph conforms to the estate contract", so the contract itself must be tamper-evident.
 *
 * Validation is a deliberate SUBSET of JSON Schema draft 2020-12: exactly the keywords
 * these four schemas use (type, const, enum, pattern, minLength, minimum, required,
 * properties, additionalProperties, items, uniqueItems, format). The subset is enforced,
 * not assumed: assertSupportedKeywords() walks every vendored schema at import and throws
 * on any validation keyword outside the set — so a future re-vendor that starts using
 * `anyOf` (say) kills the process at boot instead of silently under-validating. No ajv
 * dependency: this service is zero-web-framework by design and the closed keyword set
 * makes a hand-rolled checker complete, not approximate.
 */
import * as fs from 'node:fs'
import * as path from 'node:path'
import * as crypto from 'node:crypto'

export const SPEC_VERSION = '0.1.0' // const in every schema — pinned, not guessed

const SCHEMA_SHA256: Record<string, string> = {
  'EffectRequest.json': '99829aa50b0ebb7d663072028c37e3a29cf4cb6d2fbbbe5d6af0dda979264084',
  'EffectDecision.json': '29b7c4d9ce07b033b18f22382c3160e4eae9b56444a30cdf69b0c7a7c108d9e1',
  'OrderIntent.json': '40ff7f8a47dd4288e343aacc74c62e24b092111d5a19d3c692d88e315235f6ce',
  'ExecutionReport.json': '3eef1c1ce0e4b2bcbe0fb6f9419c0e65773f50c6b9c3e69b459f979c96ac91e1',
}

export type Json = string | number | boolean | null | Json[] | { [k: string]: Json }
type SchemaObj = Record<string, unknown>

// __dirname (CJS, per tsconfig module:commonjs — tsx serves it in both module modes);
// schemas ship beside this module (Dockerfile COPY src ./src includes src/schemas/).
const SCHEMA_DIR = path.join(__dirname, 'schemas')

// Keywords that carry validation semantics and are implemented below. Anything else
// that could change what validates (anyOf, $ref, allOf, …) must fail loudly at import.
const SUPPORTED = new Set([
  'type', 'const', 'enum', 'pattern', 'minLength', 'minimum', 'required',
  'properties', 'additionalProperties', 'items', 'uniqueItems', 'format',
])
// Pure annotations — no validation effect; safe to ignore.
const ANNOTATIONS = new Set(['$schema', '$id', 'title', 'description', 'default', 'examples'])

function assertSupportedKeywords(schema: unknown, at: string): void {
  if (Array.isArray(schema)) return void schema.forEach((v, i) => assertSupportedKeywords(v, `${at}[${i}]`))
  if (schema === null || typeof schema !== 'object') return
  for (const [k, v] of Object.entries(schema as SchemaObj)) {
    if (k === 'properties' && v && typeof v === 'object') {
      for (const [pk, pv] of Object.entries(v as SchemaObj)) assertSupportedKeywords(pv, `${at}.properties.${pk}`)
      continue
    }
    if (k === 'items' || k === 'additionalProperties') { assertSupportedKeywords(v, `${at}.${k}`); continue }
    if (SUPPORTED.has(k) || ANNOTATIONS.has(k)) continue
    throw new Error(
      `contract: schema keyword '${k}' at ${at} is outside the implemented validation subset — ` +
      'extend the validator in contract.ts (and its tests) before re-vendoring a schema that uses it')
  }
}

function loadSchema(file: string): SchemaObj {
  const bytes = fs.readFileSync(path.join(SCHEMA_DIR, file))
  const actual = crypto.createHash('sha256').update(bytes).digest('hex')
  const pinned = SCHEMA_SHA256[file]
  if (actual !== pinned) {
    throw new Error(
      `contract: vendored ${file} drifted: sha256 ${actual} != pinned ${pinned}; ` +
      're-vendor byte-identical from sourceos-spec and update contract.ts provenance')
  }
  const schema = JSON.parse(bytes.toString('utf8')) as SchemaObj
  assertSupportedKeywords(schema, file.replace(/\.json$/, ''))
  return schema
}

export const SCHEMAS: Record<'EffectRequest' | 'EffectDecision' | 'OrderIntent' | 'ExecutionReport', SchemaObj> = {
  EffectRequest: loadSchema('EffectRequest.json'),
  EffectDecision: loadSchema('EffectDecision.json'),
  OrderIntent: loadSchema('OrderIntent.json'),
  ExecutionReport: loadSchema('ExecutionReport.json'),
}

function typeOf(v: unknown): string {
  if (v === null) return 'null'
  if (Array.isArray(v)) return 'array'
  const t = typeof v
  return t === 'number' ? 'number' : t
}

function typeMatches(declared: unknown, v: unknown): boolean {
  const ts = Array.isArray(declared) ? (declared as string[]) : [String(declared)]
  const actual = typeOf(v)
  return ts.some((t) => t === actual || (t === 'integer' && actual === 'number' && Number.isInteger(v)))
}

// RFC 3339 date-time (what `format: date-time` means here) — light but real: shape + parseable.
const DATE_TIME = /^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$/

function check(schema: SchemaObj, v: unknown, at: string, errors: string[]): void {
  if (schema['type'] !== undefined && !typeMatches(schema['type'], v)) {
    errors.push(`${at}: expected type ${JSON.stringify(schema['type'])}, got ${typeOf(v)}`)
    return // wrong shape — deeper keywords would only cascade noise
  }
  if (schema['const'] !== undefined && v !== schema['const']) {
    errors.push(`${at}: must equal const ${JSON.stringify(schema['const'])}`)
  }
  if (Array.isArray(schema['enum']) && !(schema['enum'] as unknown[]).includes(v)) {
    errors.push(`${at}: must be one of ${JSON.stringify(schema['enum'])}`)
  }
  if (typeof v === 'string') {
    if (typeof schema['pattern'] === 'string' && !new RegExp(schema['pattern']).test(v)) {
      errors.push(`${at}: does not match pattern ${schema['pattern']}`)
    }
    if (typeof schema['minLength'] === 'number' && [...v].length < (schema['minLength'] as number)) {
      errors.push(`${at}: shorter than minLength ${schema['minLength']}`)
    }
    if (schema['format'] === 'date-time' && !DATE_TIME.test(v)) {
      errors.push(`${at}: not an RFC 3339 date-time`)
    }
  }
  if (typeof v === 'number' && typeof schema['minimum'] === 'number' && v < (schema['minimum'] as number)) {
    errors.push(`${at}: below minimum ${schema['minimum']}`)
  }
  if (Array.isArray(v)) {
    const items = schema['items']
    if (items && typeof items === 'object') v.forEach((x, i) => check(items as SchemaObj, x, `${at}[${i}]`, errors))
    if (schema['uniqueItems'] === true) {
      // JSON Schema uniqueness is by VALUE, and object equality is key-order
      // independent. Comparing raw JSON.stringify output made {rel,ref} and
      // {ref,rel} two different items, so a duplicate provenance link passed
      // merely by being typed in the other order — and the schemas that need
      // this are real: ExecutionReport.provenanceLinks and
      // OrderIntent.provenanceLinks are both uniqueItems arrays OF OBJECTS.
      // canonicalJson sorts keys at every depth, which is exactly the identity
      // decisionHash already seals over — one notion of "the same value" in
      // this file, not two.
      const seen = new Set(v.map((x) => canonicalJson(x as Json)))
      if (seen.size !== v.length) errors.push(`${at}: items must be unique`)
    }
  }
  if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
    const obj = v as Record<string, unknown>
    const props = (schema['properties'] ?? {}) as Record<string, SchemaObj>
    for (const r of (schema['required'] as string[] | undefined) ?? []) {
      if (!(r in obj)) errors.push(`${at}: missing required '${r}'`)
    }
    for (const [k, pv] of Object.entries(obj)) {
      if (props[k]) check(props[k]!, pv, `${at}.${k}`, errors)
      else if (schema['additionalProperties'] === false) errors.push(`${at}: unknown property '${k}'`)
      else if (schema['additionalProperties'] && typeof schema['additionalProperties'] === 'object') {
        check(schema['additionalProperties'] as SchemaObj, pv, `${at}.${k}`, errors)
      }
    }
  }
}

/** Validate a value against a vendored schema. Returns [] when conformant. */
export function validateAgainst(name: keyof typeof SCHEMAS, value: unknown): string[] {
  const errors: string[] = []
  check(SCHEMAS[name], value, name, errors)
  return errors
}

/** Canonical JSON (sorted keys, no whitespace) — the bytes decisionHash seals over. */
export function canonicalJson(value: Json): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`
  if (value !== null && typeof value === 'object') {
    const keys = Object.keys(value).sort()
    return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalJson((value as Record<string, Json>)[k]!)}`).join(',')}}`
  }
  return JSON.stringify(value)
}

export function sha256Hex(s: string): string {
  return crypto.createHash('sha256').update(s).digest('hex')
}

/** URN local-id charset per the schemas' id patterns: [A-Za-z0-9._~-]. */
export function urnLocalId(raw: string): string {
  return raw.replace(/[^A-Za-z0-9._~-]/g, '-')
}
