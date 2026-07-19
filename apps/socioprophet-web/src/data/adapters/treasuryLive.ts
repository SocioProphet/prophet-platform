import { fetchT } from './http';

// Real per-tenor US Treasury par yields from the Treasury's Daily Treasury Par Yield
// Curve XML feed (data-chart-center) — public, no key, sends `access-control-allow-origin: *`
// so it works from the browser. Returns our rate-instrument symbols → { price: yield%,
// changePct: day-over-day % change of the yield }, matching the Crypto/FX live overlay
// shape MarketMonitor merges. Fails closed (null) so the board falls back to fixture.

export interface RateQuote { price: number; changePct: number; asOf: string }

// Fixture rate instruments → Treasury curve field (tenor is an exact match, no fudging).
const TENOR_FIELD: Record<string, string> = {
  US2Y: 'BC_2YEAR',
  US10Y: 'BC_10YEAR',
  US30Y: 'BC_30YEAR',
};

const monthParam = (d: Date) => `${d.getUTCFullYear()}${String(d.getUTCMonth() + 1).padStart(2, '0')}`;

// Pull one field's Edm.Double value out of one <entry> chunk.
function field(chunk: string, name: string): number | null {
  const m = chunk.match(new RegExp(`<d:${name}[^>]*>([-0-9.]+)</d:${name}>`));
  return m ? Number(m[1]) : null;
}
function entryDate(chunk: string): string | null {
  const m = chunk.match(/<d:NEW_DATE[^>]*>([^<]+)</);
  return m ? m[1] : null;
}

function parse(xml: string): Map<string, RateQuote> | null {
  const chunks = xml.split('<entry').filter((c) => c.includes('NEW_DATE'));
  const dated = chunks.map((c) => ({ date: entryDate(c), c })).filter((e): e is { date: string; c: string } => !!e.date);
  if (dated.length < 1) return null;
  // Sort ascending by real date rather than trusting the feed's document order, so
  // latest/prior are correct even if the feed reorders or appends a placeholder.
  dated.sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
  const latest = dated[dated.length - 1];
  const prior = dated.length >= 2 ? dated[dated.length - 2] : null;
  const out = new Map<string, RateQuote>();
  for (const [symbol, fld] of Object.entries(TENOR_FIELD)) {
    const price = field(latest.c, fld);
    if (price == null) continue;
    const prev = prior ? field(prior.c, fld) : null;
    const changePct = prev && prev !== 0 ? +(((price - prev) / prev) * 100).toFixed(2) : 0;
    out.set(symbol, { price: +price.toFixed(2), changePct, asOf: latest.date.slice(0, 10) });
  }
  return out.size ? out : null;
}

export async function fetchTreasuryLive(): Promise<Map<string, RateQuote> | null> {
  const base = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value_month=';
  try {
    const now = new Date();
    const fetchMonth = async (d: Date) => {
      const res = await fetchT(`${base}${monthParam(d)}`, { headers: { accept: 'application/xml' } });
      return res.ok ? await res.text() : '';
    };
    let xml = await fetchMonth(now);
    // A day-over-day change needs TWO dated entries. Early in a month (or on the 1st business
    // day, when the current month has a single entry) pull the previous month too so the prior
    // close is real — parse() splits on <entry> and sorts by date, so concatenation is safe.
    const dateCount = (s: string) => (s.match(/<d:NEW_DATE/g) ?? []).length;
    if (dateCount(xml) < 2) {
      const prevMonth = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 1, 1));
      xml = (await fetchMonth(prevMonth)) + xml;
    }
    if (!xml.includes('NEW_DATE')) return null;
    return parse(xml);
  } catch {
    return null;
  }
}

// Exposed for unit tests (pure XML → quotes).
export const _parseTreasuryXml = parse;
