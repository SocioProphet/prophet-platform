// drugsafety-live.ts — live drug reference from the FREE public FDA label API (openFDA) and RxNorm
// (RxNav). This augments the curated interaction dataset (drugsafety.ts) with REAL, maintained,
// authoritative label data — boxed warnings, contraindications, the FDA's own drug-interaction text,
// indications — and a real RxCUI, without any commercial license. Non-diagnostic reference. Network is
// deliberately kept OUT of the hermetic CI invariants; graceful degradation means offline → null, never
// a fabricated label. The honest step from "curated 33-pair table" toward a maintained drug knowledge base.
const OPENFDA = 'https://api.fda.gov/drug/label.json';
const RXNAV = 'https://rxnav.nlm.nih.gov/REST';

const clip = (s: unknown, n = 600): string => (typeof s === 'string' ? s : Array.isArray(s) ? String(s[0] ?? '') : '').replace(/\s+/g, ' ').trim().slice(0, n);

export interface DrugLabel {
  ok: boolean;
  query: string;
  genericName?: string;
  brandNames?: string[];
  rxcui?: string;
  boxedWarning?: string;
  contraindications?: string;
  drugInteractions?: string;
  indications?: string;
  source: string;
  degraded: boolean;
  disclaimer: string;
}

async function getJson(url: string, ms = 12_000): Promise<any | null> {
  try {
    const ac = new AbortController(); const t = setTimeout(() => ac.abort(), ms);
    const r = await fetch(url, { headers: { accept: 'application/json' }, signal: ac.signal });
    clearTimeout(t);
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

// Live FDA label for a drug name. Falls back to RxNav for the RxCUI when the label omits it.
export async function fdaLabel(name: string): Promise<DrugLabel> {
  const q = (name ?? '').trim();
  const disclaimer = 'Live FDA drug-label reference (openFDA) — authoritative but summarized; non-diagnostic. Confirm dosing/interactions against the full label and a pharmacist.';
  const degraded = (): DrugLabel => ({ ok: false, query: q, source: 'openFDA', degraded: true, disclaimer: `${disclaimer} (label service unavailable)` });
  if (!q) return degraded();

  const label = await getJson(`${OPENFDA}?search=openfda.generic_name:${encodeURIComponent(q.toLowerCase())}&limit=1`);
  const r = label?.results?.[0];
  if (!r) return degraded();
  const of = r.openfda ?? {};

  let rxcui: string | undefined = Array.isArray(of.rxcui) ? of.rxcui[0] : undefined;
  if (!rxcui) { const rx = await getJson(`${RXNAV}/rxcui.json?name=${encodeURIComponent(q)}`); rxcui = rx?.idGroup?.rxnormId?.[0]; }

  return {
    ok: true, query: q,
    genericName: Array.isArray(of.generic_name) ? of.generic_name[0] : undefined,
    brandNames: Array.isArray(of.brand_name) ? of.brand_name.slice(0, 3) : undefined,
    rxcui,
    boxedWarning: r.boxed_warning ? clip(r.boxed_warning, 400) : undefined,
    contraindications: r.contraindications ? clip(r.contraindications) : undefined,
    drugInteractions: r.drug_interactions ? clip(r.drug_interactions) : undefined,
    indications: r.indications_and_usage ? clip(r.indications_and_usage, 300) : undefined,
    source: 'openFDA drug label API + RxNorm (RxNav)', degraded: false, disclaimer,
  };
}
