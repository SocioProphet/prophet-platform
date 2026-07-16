/**
 * gate.ts — the FLOOR PII gate, re-run at the aggregator on every ingest.
 *
 * The authoritative redaction happens LOCALLY in each Noetica instance (open-chat-gate.ts) before anything is
 * published — the commons never receives raw chat text. This module is the aggregator's belt-and-suspenders: it
 * re-runs the deterministic floor on ingest so a ROGUE OR BUGGY instance that publishes under-redacted text still
 * cannot poison the shared corpus with real PII. Masking already-masked text is a no-op, so running it twice is free.
 *
 * Deterministic and dependency-free (the same patterns as Noetica's redact.ts + egress-hygiene.ts floor). It masks
 * structured PII/secrets and neutralises the remote-image exfil channel. It intentionally KEEPS NO reversal mapping —
 * a commons must never be able to un-redact.
 */

// Order matters: most-specific first, so a token isn't partially eaten by a broader pattern.
const PII_PATTERNS: Array<{ kind: string; re: RegExp }> = [
  { kind: 'APIKEY', re: /\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,})\b/g },
  { kind: 'JWT', re: /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/g },
  { kind: 'EMAIL', re: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g },
  { kind: 'SSN', re: /\b\d{3}-\d{2}-\d{4}\b/g },
  { kind: 'CARD', re: /\b(?:\d[ -]?){15,16}\b/g },
  { kind: 'PHONE', re: /\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g },
  { kind: 'IP', re: /\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b/g },
]

const MD_IMAGE = /!\[[^\]]*\]\((https?:\/\/[^)]+)\)/gi

export interface FloorFindings { pii: Record<string, number>; piiCount: number; exfilUrls: string[] }
export interface FloorResult { redacted: string; findings: FloorFindings }

/**
 * Mask structured PII/secrets and neutralise remote-image exfil in `text`. Returns the safe text + a findings
 * summary. No reversal mapping is produced. Pure string work — never executes anything.
 */
export function floorGate(text: string): FloorResult {
  const kinds: Record<string, number> = {}
  const seen = new Map<string, string>()
  let out = String(text ?? '')
  for (const { kind, re } of PII_PATTERNS) {
    out = out.replace(re, (m) => {
      const prev = seen.get(m)
      if (prev) return prev
      kinds[kind] = (kinds[kind] ?? 0) + 1
      const ph = `[${kind}_${kinds[kind]}]`
      seen.set(m, ph)
      return ph
    })
  }
  // Record data-bearing remote image URLs before neutralising, then block the render channel.
  const exfilUrls: string[] = []
  for (const m of out.matchAll(MD_IMAGE)) { const u = m[1]; if (u) exfilUrls.push(u) }
  out = out.replace(MD_IMAGE, '[remote image blocked]')
  return {
    redacted: out,
    findings: { pii: kinds, piiCount: [...seen.values()].length, exfilUrls: [...new Set(exfilUrls)] },
  }
}
