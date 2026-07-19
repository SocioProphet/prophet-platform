import { fetchT } from './http';
import type { Docket } from '../lawFixture';
// Live regulatory dockets — REAL filings from the U.S. Federal Register API (public,
// no key, CORS). Turns the Law surface from an illustrative corpus into genuinely
// RETRIEVED documents with real citations (document numbers) and real source links,
// so its provenance can honestly claim 'grounded' instead of 'fixture'. Fails closed
// (null) → the surface stays on the illustrative dockets.
const ENDPOINT = 'https://www.federalregister.gov/api/v1/documents.json';

interface FrDoc { title?: string; document_number?: string; publication_date?: string; abstract?: string; html_url?: string; type?: string; agencies?: Array<{ name?: string }> }

function statusOf(type: string): Docket['status'] {
  if (/proposed/i.test(type)) return 'comment'; // proposed rules have an open comment window
  if (/rule/i.test(type)) return 'enacted';
  return 'open';
}

export async function fetchFederalRegister(limit = 25): Promise<Docket[] | null> {
  try {
    const fields = ['title', 'document_number', 'publication_date', 'abstract', 'html_url', 'type', 'agencies'];
    const qs = `per_page=${limit}&order=newest&conditions[type][]=RULE&conditions[type][]=PRORULE&` + fields.map((f) => `fields[]=${f}`).join('&');
    const res = await fetchT(`${ENDPOINT}?${qs}`, { headers: { accept: 'application/json' } }, 12000);
    if (!res.ok) return null;
    const j = (await res.json()) as { results?: FrDoc[] };
    if (!Array.isArray(j.results) || !j.results.length) return null;
    const out: Docket[] = [];
    for (const d of j.results) {
      if (!d.document_number || !d.title) continue;
      const type = d.type ?? 'Rule';
      out.push({
        id: `fr-${d.document_number}`,
        cite: d.document_number,
        title: d.title,
        type: 'rule',
        jurisdiction: 'Federal',
        status: statusOf(type),
        updated: d.publication_date ? `${d.publication_date}T00:00:00-05:00` : new Date().toISOString(),
        summary: d.abstract ?? '(no abstract provided)',
        provenanceHash: '', // real docs carry a real source link, not our placeholder hash
        redline: [],
        agency: d.agencies?.[0]?.name ?? 'U.S. Federal agency',
        tags: [type],
        affects: {},
        impact: d.abstract ?? '',
        citations: [],
        url: d.html_url,
      });
    }
    return out.length ? out : null;
  } catch {
    return null;
  }
}
