/**
 * resource.ts — dereferenceable resource descriptions (Linked-Data publishing).
 *
 * The most basic semantic-web affordance, and the one incumbents (gist/Semantic Arts, Prez, Pubby,
 * metaphactory) all ship and we didn't: paste a resource URI → get back its facts, content-negotiated.
 * `GET /api/graph/resource?uri=<iri>` returns that resource's Concise Bounded Description — every triple
 * with the URI as subject, plus back-links (triples pointing AT it) — as Turtle, JSON-LD, HTML, or JSON
 * depending on the `Accept` header. This is what makes our graph a *published* graph, not a private store.
 *
 * Serialization lives here (the engine's turtle.ts only PARSES); it reuses the store's canonical
 * `triples()` projection so a resource page can never drift from what SPARQL/Gremlin see.
 */
import type { Triple } from '@socioprophet/hellgraph'

/** Minimal store shape we depend on — just the canonical triple projection. */
export interface TripleSource { triples(): Triple[] }

export interface ResourceDescription {
  uri: string
  outgoing: Triple[]   // triples with uri as SUBJECT (the resource's own facts)
  incoming: Triple[]   // triples with uri as OBJECT  (what references it — back-links)
  found: boolean
}

/** Concise Bounded Description: the resource's own facts + inbound references. */
export function describeResource(src: TripleSource, uri: string): ResourceDescription {
  const all = src.triples()
  const outgoing = all.filter((t) => t.subject === uri)
  const incoming = all.filter((t) => t.isIri && t.object === uri)
  return { uri, outgoing, incoming, found: outgoing.length > 0 || incoming.length > 0 }
}

const VOCAB = 'https://socioprophet.ai/vocab#'

/** A predicate is either an already-prefixed CURIE (has ':') or a bare property name we mint under ph:. */
function predTerm(p: string): string {
  return p.includes(':') ? p : `ph:${sanitizeLocal(p)}`
}
function sanitizeLocal(s: string): string {
  return s.replace(/[^A-Za-z0-9_-]/g, '_') || '_'
}
function iri(s: string): string { return `<${s.replace(/[<>"\s]/g, encodeURIComponent)}>` }
function lit(v: unknown): string {
  if (typeof v === 'number' || typeof v === 'boolean') return String(v)
  return `"${String(v).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n')}"`
}
function objTerm(t: Triple): string { return t.isIri ? iri(String(t.object)) : lit(t.object) }

/** Turtle serialization of a resource's outgoing triples (the CBD subject block). */
export function toTurtle(d: ResourceDescription): string {
  const lines = [
    '@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .',
    '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .',
    `@prefix ph: <${VOCAB}> .`,
    '',
  ]
  if (d.outgoing.length === 0) {
    lines.push(`# ${d.uri} has no asserted facts (referenced by ${d.incoming.length} back-link(s))`)
  } else {
    lines.push(`${iri(d.uri)}`)
    const body = d.outgoing.map((t) => `    ${predTerm(t.predicate)} ${objTerm(t)}`)
    lines.push(body.join(' ;\n') + ' .')
  }
  return lines.join('\n') + '\n'
}

/** JSON-LD serialization (node object with @id + predicates). */
export function toJsonLd(d: ResourceDescription): unknown {
  const node: Record<string, unknown> = { '@id': d.uri }
  const types: string[] = []
  for (const t of d.outgoing) {
    if (t.predicate === 'rdf:type') { types.push(String(t.object)); continue }
    const key = t.predicate.includes(':') ? t.predicate : `${VOCAB}${sanitizeLocal(t.predicate)}`
    const val = t.isIri ? { '@id': String(t.object) } : t.object
    const cur = node[key]
    if (cur === undefined) node[key] = val
    else node[key] = Array.isArray(cur) ? [...cur, val] : [cur, val]
  }
  if (types.length) node['@type'] = types.length === 1 ? types[0] : types
  return {
    '@context': { rdf: 'http://www.w3.org/1999/02/22-rdf-syntax-ns#', ph: VOCAB },
    ...node,
    'ph:backlinks': d.incoming.map((t) => ({ '@id': t.subject, 'ph:via': t.predicate })),
  }
}

function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

/** Minimal browsable HTML view — a human can dereference the URI in a browser and read the facts. */
export function toHtml(d: ResourceDescription): string {
  const row = (p: string, o: string, isIri: boolean) =>
    `<tr><td class="p">${esc(p)}</td><td>${isIri ? `<a href="/api/graph/resource?uri=${encodeURIComponent(o)}">${esc(o)}</a>` : esc(o)}</td></tr>`
  const out = d.outgoing.map((t) => row(t.predicate, String(t.object), t.isIri)).join('')
  const inc = d.incoming.map((t) => `<tr><td>${`<a href="/api/graph/resource?uri=${encodeURIComponent(t.subject)}">${esc(t.subject)}</a>`}</td><td class="p">${esc(t.predicate)}</td></tr>`).join('')
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(d.uri)}</title>
<style>body{font:14px/1.5 system-ui,sans-serif;max-width:56rem;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
h1{font-size:1.1rem;word-break:break-all}h2{font-size:.9rem;color:#666;margin-top:2rem}
table{border-collapse:collapse;width:100%}td{border-top:1px solid #eee;padding:.35rem .6rem;vertical-align:top}
.p{color:#555;white-space:nowrap;font-family:ui-monospace,monospace}a{color:#0645ad;text-decoration:none}
a:hover{text-decoration:underline}.empty{color:#999}
@media(prefers-color-scheme:dark){body{background:#111;color:#ddd}td{border-color:#333}.p{color:#9aa}a{color:#6ab0ff}}</style>
</head><body>
<h1>${esc(d.uri)}</h1>
${d.outgoing.length ? `<h2>Facts (${d.outgoing.length})</h2><table>${out}</table>` : '<p class="empty">No asserted facts.</p>'}
${d.incoming.length ? `<h2>Referenced by (${d.incoming.length})</h2><table>${inc}</table>` : ''}
<p style="margin-top:2rem;color:#999">Turtle · JSON-LD via <code>Accept</code> header — a proof-carrying HellGraph resource.</p>
</body></html>`
}

export type ResourceFormat = 'turtle' | 'jsonld' | 'html' | 'json'

/** Content-negotiate on the Accept header. Browser (text/html) → HTML; RDF clients → turtle/jsonld; else JSON. */
export function negotiate(accept: string | undefined): ResourceFormat {
  const a = (accept ?? '').toLowerCase()
  if (a.includes('text/turtle') || a.includes('application/x-turtle')) return 'turtle'
  if (a.includes('application/ld+json')) return 'jsonld'
  if (a.includes('text/html') || a.includes('application/xhtml')) return 'html'
  return 'json'
}
