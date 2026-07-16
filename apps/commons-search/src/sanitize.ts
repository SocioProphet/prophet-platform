/**
 * sanitize.ts — strip prompt-injection directives from commons snippets before they are served.
 *
 * An open chat is UNTRUSTED input to every OTHER user's agent — a place someone could plant "ignore previous
 * instructions…" to hijack a searcher's agent. This deterministically neutralises the common directive shapes in a
 * snippet (mirrors Noetica's sanitizeRetrieved). Defense in depth: the reader's web_search layer additionally marks
 * the whole result as EXTERNAL, and the gate already removed remote-image exfil. Pure string work — executes nothing.
 */
const INJECTION_PATTERNS: RegExp[] = [
  /ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?/gi,
  /disregard\s+(?:all\s+)?(?:previous|prior|above)[^.\n]*/gi,
  /you\s+are\s+now\s+[^.\n]*/gi,
  /new\s+(?:system\s+)?(?:instructions?|prompt)\s*:/gi,
  /\bsystem\s*prompt\s*:/gi,
  /###\s*(?:system|instruction)/gi,
]

export function sanitizeSnippet(text: string): string {
  let out = String(text ?? '')
  for (const re of INJECTION_PATTERNS) out = out.replace(re, '[redacted-instruction]')
  return out
}
