// Portfolio agent — OUR agent, not a cloud provider's. A small registry of
// deterministic, proof-carrying tools plus a driver that runs them over the
// paper book. Every finding is verified-compute (replayable from its inputs);
// the tools are also published as a manifest so the mesh / Noetica can call the
// exact same functions the cockpit panel does — one tool layer, two callers.
import { instruments } from '../data/marketsFixture';
import { prov, type Provenance } from '../features/provenance/types';

// ---- Types -----------------------------------------------------------------
export interface BookPosition {
  symbol: string; name: string; qty: number; avgCost: number;
  last: number; mv: number; upl: number; klass: string; series: number[];
}
export type Severity = 'info' | 'watch' | 'alert';
export interface Finding { id: string; severity: Severity; title: string; detail: string; prov: Provenance; }
export interface ProposedOrder {
  symbol: string; name: string; side: 'buy' | 'sell'; qty: number; price: number; rationale: string;
}
export interface AgentResult {
  goal: string; findings: Finding[]; actions: ProposedOrder[];
  narrative: string; tools: string[]; prov: Provenance;
}

// Tool manifest — the contract the mesh / Noetica calls against (same fns below).
export interface ToolSpec { name: string; description: string; params: string; returns: string; }
export const PORTFOLIO_TOOLS: ToolSpec[] = [
  { name: 'exposure',      description: 'Net weight by asset class', params: 'book', returns: 'weights[]' },
  { name: 'concentration', description: 'Herfindahl index + top-name weight; flags single-name risk', params: 'book', returns: 'finding' },
  { name: 'risk',          description: '1-day 95% parametric VaR from realized vol (correlation=1, conservative)', params: 'book, equity', returns: 'finding' },
  { name: 'rebalance',     description: 'Trim overweight names to a target max weight; returns paper orders', params: 'book, equity, maxWeight', returns: 'orders[]' },
];

// ---- Deterministic primitives ---------------------------------------------
const priceMap = new Map(instruments.map((i) => [i.symbol, i]));

// djb2 content id over the tool inputs — an honest deterministic receipt (not a
// cryptographic claim): same inputs → same id, so a finding is replay-checkable.
function contentId(input: unknown): string {
  const s = JSON.stringify(input);
  let h = 5381; for (let i = 0; i < s.length; i += 1) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return `id:pf-${(h >>> 0).toString(16).padStart(8, '0')}`;
}

// Daily-return stdev from a price series (sample stdev), scaled to a 1-day move.
function dailyVol(series: number[]): number {
  if (!series || series.length < 3) return 0.02; // fixture fallback
  const rets: number[] = [];
  for (let i = 1; i < series.length; i += 1) {
    const prev = series[i - 1]!; if (prev) rets.push(series[i]! / prev - 1);
  }
  const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
  const varc = rets.reduce((a, r) => a + (r - mean) ** 2, 0) / Math.max(1, rets.length - 1);
  return Math.sqrt(varc);
}

const CLASS_LABEL: Record<string, string> = {
  index: 'Indices', equity: 'Equities', preferred: 'Preferreds', bond: 'Bonds',
  rate: 'Rates', option: 'Options', fx: 'FX', crypto: 'Crypto',
  commodity: 'Commodities', 'real-asset': 'Real assets', alt: 'Alternatives',
};

// ---- Tools -----------------------------------------------------------------
export interface ExposureRow { klass: string; label: string; weight: number; mv: number; }
export function exposure(book: BookPosition[]): ExposureRow[] {
  const total = book.reduce((s, p) => s + p.mv, 0) || 1;
  const byClass = new Map<string, number>();
  for (const p of book) byClass.set(p.klass, (byClass.get(p.klass) ?? 0) + p.mv);
  return [...byClass.entries()]
    .map(([klass, mv]) => ({ klass, label: CLASS_LABEL[klass] ?? klass, mv, weight: mv / total }))
    .sort((a, b) => b.weight - a.weight);
}

export function concentration(book: BookPosition[]): Finding {
  const total = book.reduce((s, p) => s + p.mv, 0) || 1;
  const weights = book.map((p) => ({ symbol: p.symbol, w: p.mv / total }));
  const hhi = weights.reduce((s, x) => s + x.w * x.w, 0);
  const top = weights.slice().sort((a, b) => b.w - a.w)[0];
  const effN = hhi ? 1 / hhi : 0;
  const sev: Severity = top && top.w > 0.4 ? 'alert' : top && top.w > 0.25 ? 'watch' : 'info';
  const topPct = top ? (top.w * 100).toFixed(1) : '0';
  return {
    id: 'concentration',
    severity: sev,
    title: sev === 'info' ? 'Diversified book' : `Concentrated in ${top?.symbol}`,
    detail: `Herfindahl index ${hhi.toFixed(3)} (~${effN.toFixed(1)} effective names). Largest position ${top?.symbol ?? '—'} is ${topPct}% of the book`
      + (sev === 'info' ? '.' : sev === 'watch' ? ' — above the 25% single-name guardrail.' : ' — a dominant single-name exposure.'),
    prov: prov('computed', {
      verifier: 'portfolio agent',
      formula: 'HHI = Σ wᵢ² ; effective names = 1/HHI ; wᵢ = mvᵢ / Σmv',
      sources: ['order blotter', 'Market Monitor marks'],
      receipt: contentId(weights),
      note: 'Deterministic — replayable from the position weights.',
    }),
  };
}

export function risk(book: BookPosition[], equity: number): Finding {
  const total = book.reduce((s, p) => s + p.mv, 0) || 1;
  // correlation=1 (conservative): portfolio 1-day σ = Σ wᵢ·σᵢ
  const portDailyVol = book.reduce((s, p) => s + (p.mv / total) * dailyVol(p.series), 0);
  const z = 1.645; // 95% one-tailed
  const marketValue = book.reduce((s, p) => s + p.mv, 0);
  const var95 = z * portDailyVol * marketValue;
  const varPctEq = equity ? (var95 / equity) * 100 : 0;
  const sev: Severity = varPctEq > 5 ? 'alert' : varPctEq > 2.5 ? 'watch' : 'info';
  return {
    id: 'risk',
    severity: sev,
    title: `1-day VaR ≈ ${fmtMoney(var95)} (95%)`,
    detail: `At 95% confidence the book should not lose more than ~${fmtMoney(var95)} in a day `
      + `(${varPctEq.toFixed(1)}% of equity). Portfolio 1-day σ ${(portDailyVol * 100).toFixed(2)}%, `
      + `realized from each holding's price series, aggregated correlation=1 (conservative).`,
    prov: prov('computed', {
      verifier: 'portfolio agent',
      formula: 'VaR₉₅ = 1.645 · σ_p · MV ; σ_p = Σ wᵢ·σᵢ ; σᵢ = stdev(daily returns)',
      sources: ['order blotter', 'Market Monitor price series'],
      receipt: contentId(book.map((p) => [p.symbol, p.mv, dailyVol(p.series)])),
      note: 'Parametric VaR, correlation=1 upper bound. Deterministic from the marks.',
    }),
  };
}

export function rebalance(book: BookPosition[], equity: number, maxWeight = 0.2): ProposedOrder[] {
  const total = book.reduce((s, p) => s + p.mv, 0) || 1;
  const cap = maxWeight * total;
  const orders: ProposedOrder[] = [];
  for (const p of book) {
    if (p.mv <= cap) continue;
    const sellMv = p.mv - cap;
    const qty = Math.floor(sellMv / (p.last || p.avgCost || 1));
    if (qty <= 0) continue;
    orders.push({
      symbol: p.symbol, name: p.name, side: 'sell', qty, price: p.last,
      rationale: `Trim to ${(maxWeight * 100).toFixed(0)}% max weight (was ${((p.mv / total) * 100).toFixed(1)}%).`,
    });
  }
  return orders;
}

// ---- Driver ----------------------------------------------------------------
// Given a plain-language goal, select + run the relevant tools and assemble a
// proof-carrying result. Pure and synchronous — no cloud round-trip.
export function runPortfolioAgent(goal: string, book: BookPosition[], equity: number): AgentResult {
  const g = goal.toLowerCase();
  const used: string[] = [];
  const findings: Finding[] = [];
  let actions: ProposedOrder[] = [];

  if (book.length === 0) {
    return {
      goal, findings: [], actions: [], tools: [],
      narrative: 'The paper book is empty — open the Market Monitor and place an order, then rerun the agent to get a risk and concentration read.',
      prov: prov('computed', { verifier: 'portfolio agent', note: 'No positions to analyze.' }),
    };
  }

  // Always assay concentration + risk (the core read).
  const conc = concentration(book); findings.push(conc); used.push('concentration');
  const rk = risk(book, equity); findings.push(rk); used.push('risk');

  // Exposure finding (informational).
  const exp = exposure(book); used.push('exposure');
  const topExp = exp[0];
  if (topExp) {
    findings.push({
      id: 'exposure',
      severity: topExp.weight > 0.6 ? 'watch' : 'info',
      title: `${(topExp.weight * 100).toFixed(0)}% ${topExp.label}`,
      detail: `Asset-class mix: ${exp.map((e) => `${e.label} ${(e.weight * 100).toFixed(0)}%`).join(' · ')}.`,
      prov: prov('computed', {
        verifier: 'portfolio agent',
        formula: 'weight_class = Σ mv(class) / Σ mv',
        sources: ['order blotter', 'instrument asset-class tags'],
        receipt: contentId(exp.map((e) => [e.klass, +e.weight.toFixed(4)])),
      }),
    });
  }

  // If the goal is about de-risking/rebalancing/trimming, propose orders.
  const wantsRebalance = /rebalanc|trim|reduce|de-?risk|concentrat|risk|diversif|cut/.test(g);
  if (wantsRebalance) {
    actions = rebalance(book, equity, 0.2); used.push('rebalance');
  }

  // Narrative — a plain call built from the assayed findings (no free generation).
  const parts: string[] = [];
  parts.push(conc.severity === 'info'
    ? 'The book is reasonably diversified.'
    : `Concentration is elevated — ${conc.title.toLowerCase()}.`);
  parts.push(rk.severity === 'info'
    ? `Daily downside looks contained (${rk.title}).`
    : `Daily downside is meaningful (${rk.title}).`);
  if (actions.length) {
    parts.push(`Proposed ${actions.length} trim${actions.length === 1 ? '' : 's'} to a 20% single-name cap — stage any you accept into the paper book.`);
  } else if (wantsRebalance) {
    parts.push('No position breaches the 20% cap, so no trims are needed.');
  }

  return {
    goal,
    findings,
    actions,
    tools: used,
    narrative: parts.join(' '),
    prov: prov('computed', {
      verifier: 'portfolio agent',
      sources: ['order blotter', 'Market Monitor marks'],
      receipt: contentId({ goal, book: book.map((p) => [p.symbol, p.qty, p.last]), equity }),
      note: 'Every finding is deterministic verified-compute; the agent selects tools, it does not invent numbers.',
    }),
  };
}

export function bookFromPositions(
  positions: { symbol: string; name: string; qty: number; avgCost: number }[],
): BookPosition[] {
  return positions.filter((p) => p.qty > 0).map((p) => {
    const inst = priceMap.get(p.symbol);
    const last = inst?.price ?? p.avgCost;
    return {
      symbol: p.symbol, name: p.name, qty: p.qty, avgCost: p.avgCost,
      last, mv: last * p.qty, upl: (last - p.avgCost) * p.qty,
      klass: inst?.klass ?? 'equity', series: inst?.series ?? [],
    };
  });
}

function fmtMoney(n: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(n);
}

// ── Portfolio ② — our OWN sovereign cloud agent. The same tool layer, run server-side by the
// deployed portfolio-agent service (/svc/portfolio). "Both ways": ① is this in-browser, ② is the
// cloud. Best-effort — returns null on failure so the caller can fall back to the local ① run.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function cloudFinding(f: any): Finding {
  return {
    id: String(f.id), severity: f.severity, title: String(f.title), detail: String(f.detail),
    prov: prov('computed', {
      verifier: 'portfolio-agent (sovereign cloud)', formula: f.formula, receipt: f.receipt,
      note: 'Computed by our own cloud agent — replayable from its inputs, not a third-party.',
    }),
  };
}
export async function runCloudAgent(goal: string, book: BookPosition[], equity: number): Promise<AgentResult | null> {
  try {
    const res = await fetch('/svc/portfolio/analyze', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        goal, equity,
        positions: book.map((p) => ({ symbol: p.symbol, name: p.name, qty: p.qty, avgCost: p.avgCost, last: p.last, series: p.series })),
      }),
    });
    if (!res.ok) return null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const d = (await res.json()) as any;
    return {
      goal: d.goal ?? goal,
      findings: (d.findings ?? []).map(cloudFinding),
      actions: d.actions ?? [],
      narrative: d.narrative ?? '',
      tools: d.tools ?? [],
      prov: prov('computed', {
        verifier: d.engine ?? 'portfolio-agent (sovereign cloud)', receipt: d.receipt,
        note: 'Our own cloud agent — we roll our own, not a third-party cloud provider.',
      }),
    };
  } catch {
    return null;
  }
}
