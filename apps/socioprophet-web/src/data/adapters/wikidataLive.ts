import { fetchT } from './http';
// Live People/OSINT adapter — real people & organizations from Wikidata (no key,
// CORS via origin=*). Search resolves candidate entities; a details call pulls the
// claims we can map to the directory's Entity shape (kind, description, website,
// X, GitHub → accounts/selectors), with the Wikidata QID as real provenance. Live
// entities are naturally sparser than the rich fixtures — that's honest. Fails
// closed (null) → the directory stays on fixture.
import type { Entity } from '../peopleFixture';

interface SearchHit { id: string; label?: string; description?: string }

interface Claim { mainsnak?: { datavalue?: { value?: unknown } } }
interface WdEntity {
  labels?: { en?: { value?: string } };
  descriptions?: { en?: { value?: string } };
  claims?: Record<string, Claim[]>;
}

const strVal = (claims: Record<string, Claim[]> | undefined, prop: string): string | undefined => {
  const v = claims?.[prop]?.[0]?.mainsnak?.datavalue?.value;
  return typeof v === 'string' ? v : undefined;
};
const hasEntity = (claims: Record<string, Claim[]> | undefined, prop: string, qid: string): boolean =>
  (claims?.[prop] ?? []).some((c) => {
    const v = c.mainsnak?.datavalue?.value as { id?: string } | undefined;
    return v?.id === qid;
  });

export async function fetchPeopleLive(query: string, limit = 12): Promise<Entity[] | null> {
  try {
    const q = (query || 'economist').trim();
    const searchUrl = `https://www.wikidata.org/w/api.php?action=wbsearchentities&search=${encodeURIComponent(q)}&language=en&type=item&limit=${limit}&format=json&origin=*`;
    const sres = await fetchT(searchUrl);
    if (!sres.ok) return null;
    const sj = (await sres.json()) as { search?: SearchHit[] };
    const hits = (sj.search ?? []).filter((h) => h.id && h.label);
    if (!hits.length) return null;
    // Details for kind + social handles.
    const ids = hits.map((h) => h.id).join('|');
    const dUrl = `https://www.wikidata.org/w/api.php?action=wbgetentities&ids=${ids}&props=claims|descriptions|labels&languages=en&format=json&origin=*`;
    let details: Record<string, WdEntity> = {};
    try {
      const dres = await fetchT(dUrl);
      if (dres.ok) details = ((await dres.json()) as { entities?: Record<string, WdEntity> }).entities ?? {};
    } catch { /* details are best-effort */ }
    return hits.map((h): Entity => {
      const d = details[h.id];
      const claims = d?.claims;
      const isPerson = hasEntity(claims, 'P31', 'Q5');
      const website = strVal(claims, 'P856');
      const twitter = strVal(claims, 'P2002');
      const github = strVal(claims, 'P2037');
      const accounts: Entity['accounts'] = [];
      if (twitter) accounts.push({ platform: 'x', handle: `@${twitter}`, url: `https://x.com/${twitter}`, verified: true });
      if (github) accounts.push({ platform: 'github', handle: github, url: `https://github.com/${github}` });
      if (website) accounts.push({ platform: 'web', handle: website.replace(/^https?:\/\//, '').replace(/\/$/, ''), url: website });
      const selectors: Entity['selectors'] = [];
      if (twitter) selectors.push({ kind: 'username', value: twitter });
      if (website) { try { selectors.push({ kind: 'domain', value: new URL(website).hostname }); } catch { /* skip */ } }
      const desc = h.description ?? d?.descriptions?.en?.value ?? '';
      return {
        id: `wd-${h.id}`,
        name: h.label ?? h.id,
        kind: isPerson ? 'person' : 'org',
        role: desc.slice(0, 60),
        affiliation: '',
        location: '',
        tags: [],
        confidence: 1,
        sources: accounts.length + 1,
        summary: desc,
        relations: [],
        accounts,
        selectors,
        osint: [{ name: `Wikidata ${h.id}`, kind: 'registry', confidence: 1 }],
      };
    });
  } catch {
    return null;
  }
}
