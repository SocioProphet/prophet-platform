// Portfolio agent — the sovereign CLOUD agent (Portfolio ②). Same proof-carrying tool layer the
// cockpit runs in-browser (①), but server-side so it can run autonomously / on a schedule and the
// cockpit can call OUR agent instead of yielding to a third-party cloud agent. Pure + deterministic:
// every finding is verified-compute (replayable from its inputs), carrying a content-id receipt.

export interface Position {
  symbol: string;
  name: string;
  qty: number;
  avgCost: number;
  last: number;
  klass?: string;
  series?: number[];
}
export type Severity = 'info' | 'watch' | 'alert';
export interface Finding { id: string; severity: Severity; title: string; detail: string; formula: string; receipt: string }
export interface ProposedOrder { symbol: string; name: string; side: 'buy' | 'sell'; qty: number; price: number; rationale: string }
export interface AgentResult {
  goal: string;
  findings: Finding[];
  actions: ProposedOrder[];
  narrative: string;
  tools: string[];
  receipt: string;
  engine: string;
  attested: boolean;
}

// djb2 content id over inputs — an honest deterministic receipt (same inputs → same id, replay-checkable).
function contentId(input: unknown): string {
  const s = JSON.stringify(input);
  let h = 5381;
  for (let i = 0; i < s.length; i += 1) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return `id:pf-${(h >>> 0).toString(16).padStart(8, '0')}`;
}

// Sample stdev of daily returns from a price series, scaled to a 1-day move.
function dailyVol(series?: number[]): number {
  if (!series || series.length < 3) return 0.02;
  const rets: number[] = [];
  for (let i = 1; i < series.length; i += 1) { const p = series[i - 1]!; if (p) rets.push(series[i]! / p - 1); }
  const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
  const varc = rets.reduce((a, r) => a + (r - mean) ** 2, 0) / Math.max(1, rets.length - 1);
  return Math.sqrt(varc);
}

function mv(p: Position): number { return p.last * p.qty; }

export function concentration(book: Position[]): Finding {
  const total = book.reduce((s, p) => s + mv(p), 0) || 1;
  const weights = book.map((p) => ({ symbol: p.symbol, w: mv(p) / total }));
  const hhi = weights.reduce((s, x) => s + x.w * x.w, 0);
  const top = weights.slice().sort((a, b) => b.w - a.w)[0];
  const effN = hhi ? 1 / hhi : 0;
  const sev: Severity = top && top.w > 0.4 ? 'alert' : top && top.w > 0.25 ? 'watch' : 'info';
  const topPct = top ? (top.w * 100).toFixed(1) : '0';
  return {
    id: 'concentration', severity: sev,
    title: sev === 'info' ? 'Diversified book' : `Concentrated in ${top?.symbol}`,
    detail: `Herfindahl index ${hhi.toFixed(3)} (~${effN.toFixed(1)} effective names). Largest position ${top?.symbol ?? '—'} is ${topPct}% of the book`
      + (sev === 'info' ? '.' : sev === 'watch' ? ' — above the 25% single-name guardrail.' : ' — a dominant single-name exposure.'),
    formula: 'HHI = Σ wᵢ² ; effective names = 1/HHI ; wᵢ = mvᵢ / Σmv',
    receipt: contentId(weights),
  };
}

export function risk(book: Position[], equity: number): Finding {
  const total = book.reduce((s, p) => s + mv(p), 0) || 1;
  const portDailyVol = book.reduce((s, p) => s + (mv(p) / total) * dailyVol(p.series), 0);
  const marketValue = book.reduce((s, p) => s + mv(p), 0);
  const var95 = 1.645 * portDailyVol * marketValue;
  const varPctEq = equity ? (var95 / equity) * 100 : 0;
  const sev: Severity = varPctEq > 5 ? 'alert' : varPctEq > 2.5 ? 'watch' : 'info';
  return {
    id: 'risk', severity: sev,
    title: `1-day VaR ≈ ${fmtMoney(var95)} (95%)`,
    detail: `At 95% confidence the book should not lose more than ~${fmtMoney(var95)} in a day (${varPctEq.toFixed(1)}% of equity). `
      + `Portfolio 1-day σ ${(portDailyVol * 100).toFixed(2)}%, realized per holding, aggregated correlation=1 (conservative).`,
    formula: 'VaR₉₅ = 1.645 · σ_p · MV ; σ_p = Σ wᵢ·σᵢ ; σᵢ = stdev(daily returns)',
    receipt: contentId(book.map((p) => [p.symbol, mv(p), dailyVol(p.series)])),
  };
}

export function rebalance(book: Position[], maxWeight = 0.2): ProposedOrder[] {
  const total = book.reduce((s, p) => s + mv(p), 0) || 1;
  const cap = maxWeight * total;
  const orders: ProposedOrder[] = [];
  for (const p of book) {
    if (mv(p) <= cap) continue;
    const qty = Math.floor((mv(p) - cap) / (p.last || p.avgCost || 1));
    if (qty <= 0) continue;
    orders.push({ symbol: p.symbol, name: p.name, side: 'sell', qty, price: p.last,
      rationale: `Trim to ${(maxWeight * 100).toFixed(0)}% max weight (was ${((mv(p) / total) * 100).toFixed(1)}%).` });
  }
  return orders;
}

export function runPortfolioAgent(goal: string, book: Position[], equity: number): AgentResult {
  const engine = 'portfolio-agent (sovereign cloud)';
  if (book.length === 0) {
    return { goal, findings: [], actions: [], tools: [], narrative: 'Empty book — nothing to analyze.', receipt: contentId({ goal }), engine, attested: true };
  }
  const used: string[] = [];
  const conc = concentration(book); used.push('concentration');
  const rk = risk(book, equity); used.push('risk');
  const findings = [conc, rk];

  let actions: ProposedOrder[] = [];
  if (/rebalanc|trim|reduce|de-?risk|concentrat|risk|diversif|cut/.test(goal.toLowerCase())) {
    actions = rebalance(book, 0.2); used.push('rebalance');
  }

  const parts: string[] = [];
  parts.push(conc.severity === 'info' ? 'The book is reasonably diversified.' : `Concentration is elevated — ${conc.title.toLowerCase()}.`);
  parts.push(rk.severity === 'info' ? `Daily downside looks contained (${rk.title}).` : `Daily downside is meaningful (${rk.title}).`);
  if (actions.length) parts.push(`Proposed ${actions.length} trim${actions.length === 1 ? '' : 's'} to a 20% single-name cap.`);

  return {
    goal, findings, actions, tools: used, narrative: parts.join(' '),
    receipt: contentId({ goal, book: book.map((p) => [p.symbol, p.qty, p.last]), equity }),
    engine, attested: true,
  };
}

function fmtMoney(n: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(n);
}
