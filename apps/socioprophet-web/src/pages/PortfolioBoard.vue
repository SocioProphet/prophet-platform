<template>
  <section class="pf" aria-label="Portfolio">
    <SurfaceHeader title='Portfolio' eyebrow="Capital &amp; Markets">
      <template #badge><span class="pf-pill">paper</span></template>
      <template #actions>
        <div class="pf-actions">
        <button class="pf-agent-btn" type="button" @click="runAgent" title="Run our proof-carrying portfolio agent">◆ Run agent</button>
        <button class="pf-ask" type="button" @click="askNoetica">◇ Ask Noetica</button>
        <button class="pf-reset" type="button" @click="portfolio.reset()" title="Clear the paper book">Reset book</button>
        </div>
      </template>
    </SurfaceHeader>

    <!-- Account summary -->
    <div class="pf-summary">
      <div class="pf-stat">
        <span class="pf-s-label">Equity</span>
        <span class="pf-s-val">{{ money(equity) }}</span>
        <span class="pf-s-sub">cash {{ money(portfolio.cash) }}</span>
      </div>
      <div class="pf-stat">
        <span class="pf-s-label">Total P&amp;L <ProvenanceBadge :p="pnlProv" compact /></span>
        <span class="pf-s-val" :class="pnlDir(totalPnl)">{{ signed(totalPnl) }}</span>
        <span class="pf-s-sub">{{ (equity ? (totalPnl / portfolio.startingCash) * 100 : 0).toFixed(2) }}% of start</span>
      </div>
      <div class="pf-stat">
        <span class="pf-s-label">Unrealized</span>
        <span class="pf-s-val" :class="pnlDir(unrealized)">{{ signed(unrealized) }}</span>
        <span class="pf-s-sub">marked to market</span>
      </div>
      <div class="pf-stat">
        <span class="pf-s-label">Realized</span>
        <span class="pf-s-val" :class="pnlDir(portfolio.realized)">{{ signed(portfolio.realized) }}</span>
        <span class="pf-s-sub">{{ rows.length }} position(s) · {{ portfolio.blotter.length }} fill(s)</span>
      </div>
    </div>

    <!-- Portfolio agent — our tool layer, run in-cockpit (not a cloud provider). -->
    <div v-if="agentOpen" class="pf-agent">
      <div class="pf-agent-bar">
        <input
          v-model="agentGoal"
          class="pf-agent-goal"
          type="text"
          placeholder="Goal for the agent…"
          @keydown.enter="runAgent"
        />
        <button class="pf-agent-run" type="button" @click="runAgent">Run</button>
        <button class="pf-agent-x" type="button" title="Close" @click="agentOpen = false">×</button>
      </div>

      <template v-if="agentResult">
        <p class="pf-agent-narrative">
          {{ agentResult.narrative }}
          <ProvenanceBadge :p="agentResult.prov" compact />
        </p>
        <p class="pf-agent-tools">
          Tools run: <span v-for="t in agentResult.tools" :key="t" class="pf-tool-chip">{{ t }}</span>
          <span class="pf-tool-sep">·</span>
          <span class="pf-tool-note">same functions the mesh calls ({{ PORTFOLIO_TOOLS.length }} published)</span>
        </p>

        <div v-if="agentResult.findings.length" class="pf-findings">
          <div v-for="f in agentResult.findings" :key="f.id" class="pf-finding" :class="f.severity">
            <span class="pf-f-sev">{{ sevGlyph(f.severity) }}</span>
            <div class="pf-f-body">
              <div class="pf-f-title">{{ f.title }} <ProvenanceBadge :p="f.prov" compact /></div>
              <div class="pf-f-detail">{{ f.detail }}</div>
            </div>
          </div>
        </div>

        <div v-if="agentResult.actions.length" class="pf-proposed">
          <div class="pf-proposed-h">Proposed orders <span class="pf-hint">stage into the paper book</span></div>
          <div v-for="(a, i) in agentResult.actions" :key="`${a.symbol}-${i}`" class="pf-proposed-row">
            <span class="pf-fill-side" :class="a.side">{{ a.side === 'buy' ? 'BUY' : 'SELL' }}</span>
            <span class="pf-p-sym">{{ a.symbol }}</span>
            <span class="pf-p-qty">{{ a.qty }} @ {{ num(a.price) }}</span>
            <span class="pf-p-why">{{ a.rationale }}</span>
            <button
              class="pf-p-stage"
              type="button"
              :disabled="staged.has(`${a.symbol}-${i}`)"
              @click="stageOrder(a, i)"
            >{{ staged.has(`${a.symbol}-${i}`) ? '✓ staged' : 'Stage' }}</button>
          </div>
        </div>
      </template>
    </div>

    <SplitPane storage-key="portfolio" label="holdings" :initial="380">
      <template #list>
      <!-- Positions -->
      <div class="pf-panel">
        <div class="pf-panel-h">Positions</div>
        <p v-if="rows.length === 0" class="pf-empty">
          No positions yet. Open the <RouterLink class="pf-link" to="/markets/indices-funds">Market Monitor</RouterLink>,
          pick any instrument across asset classes, and place an order — it posts here.
        </p>
        <div v-else class="pf-table" role="table">
          <div class="pf-row pf-row-head" role="row">
            <span>Symbol</span><span class="r">Qty</span><span class="r">Avg</span><span class="r">Last</span><span class="r">Mkt value</span><span class="r">Unreal. P&amp;L</span>
          </div>
          <button v-for="r in rows" :key="r.symbol" class="pf-row" role="row" @click="openSymbol(r.symbol)">
            <span class="pf-sym"><b>{{ r.symbol }}</b><small>{{ r.name }}</small></span>
            <span class="r">{{ r.qty }}</span>
            <span class="r">{{ num(r.avgCost) }}</span>
            <span class="r">{{ num(r.last) }}</span>
            <span class="r">{{ money(r.mv) }}</span>
            <span class="r" :class="pnlDir(r.upl)">{{ signed(r.upl) }} <small>({{ r.uplPct >= 0 ? '+' : '' }}{{ r.uplPct.toFixed(1) }}%)</small></span>
          </button>
        </div>
      </div>
      </template>

      <template #detail>

      <!-- Blotter -->
      <div class="pf-panel">
        <div class="pf-panel-h">Blotter <span class="pf-hint">all fills · manual + algo</span></div>
        <p v-if="portfolio.blotter.length === 0" class="pf-empty">No fills yet.</p>
        <div v-else class="pf-blotter">
          <div v-for="o in portfolio.blotter" :key="o.id" class="pf-fill" @click="openSymbol(o.symbol)">
            <span class="pf-fill-side" :class="o.side">{{ o.side === 'buy' ? 'BUY' : 'SELL' }}</span>
            <span class="pf-fill-sym">{{ o.symbol }}</span>
            <span class="pf-fill-qty">{{ o.qty }} @ {{ num(o.price) }}</span>
            <span class="pf-fill-src">{{ o.source }}</span>
            <span class="pf-fill-ts">{{ time(o.ts) }}</span>
          </div>
        </div>
        <p class="pf-prov">Paper book · deterministic client-side state · persisted locally. Marks use the Market Monitor's fixture quotes.</p>
      </div>
      </template>
    </SplitPane>
  </section>
</template>

<script setup lang="ts">
import SurfaceHeader from '../components/SurfaceHeader.vue';
import SplitPane from '../components/SplitPane.vue';
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { instruments } from '../data/marketsFixture';
import { usePortfolio } from '../stores/portfolio';
import { useCockpit } from '../stores/cockpit';
import ProvenanceBadge from '../components/ProvenanceBadge.vue';
import { prov } from '../features/provenance/types';
import { runPortfolioAgent, bookFromPositions, PORTFOLIO_TOOLS, type AgentResult, type ProposedOrder } from '../services/portfolioAgent';

// P&L is deterministic compute from the blotter + marks — the verified-compute moat.
const pnlProv = prov('computed', {
  verifier: 'portfolio engine',
  formula: 'Σ (last − avgCost)·qty + realized',
  sources: ['order blotter', 'Market Monitor marks'],
  receipt: 'sha256:pf-mtm-0x',
  note: 'Marks use fixture quotes; the P&L computation itself is deterministic and replayable.',
});

const router = useRouter();
const portfolio = usePortfolio();
const cockpit = useCockpit();

const priceMap = new Map(instruments.map((i) => [i.symbol, i]));

const rows = computed(() =>
  portfolio.positions.filter((p) => p.qty > 0).map((p) => {
    const inst = priceMap.get(p.symbol);
    const last = inst?.price ?? p.avgCost;
    const mv = last * p.qty;
    const upl = (last - p.avgCost) * p.qty;
    const uplPct = p.avgCost ? ((last - p.avgCost) / p.avgCost) * 100 : 0;
    return { ...p, last, mv, upl, uplPct };
  }),
);
const marketValue = computed(() => rows.value.reduce((s, r) => s + r.mv, 0));
const equity = computed(() => portfolio.cash + marketValue.value);
const unrealized = computed(() => rows.value.reduce((s, r) => s + r.upl, 0));
const totalPnl = computed(() => unrealized.value + portfolio.realized);

const money = (n: number): string => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(n);
const num = (n: number): string => n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const signed = (n: number): string => `${n >= 0 ? '+' : '−'}${money(Math.abs(n))}`;
const pnlDir = (n: number): 'up' | 'down' | 'flat' => (n > 0.005 ? 'up' : n < -0.005 ? 'down' : 'flat');
const time = (ts: number): string => new Date(ts).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });

// --- Portfolio agent (OUR tool layer — deterministic, proof-carrying) --------
const agentGoal = ref('Reduce concentration and size my downside risk');
const agentResult = ref<AgentResult | null>(null);
const agentOpen = ref(false);
const staged = ref<Set<string>>(new Set());
function runAgent() {
  const book = bookFromPositions(portfolio.positions);
  agentResult.value = runPortfolioAgent(agentGoal.value, book, equity.value);
  staged.value = new Set();
  agentOpen.value = true;
}
function stageOrder(a: ProposedOrder, i: number) {
  const res = portfolio.placeOrder({ symbol: a.symbol, name: a.name, side: a.side, qty: a.qty, price: a.price, source: 'agent:rebalance' });
  if (res.ok) staged.value = new Set(staged.value).add(`${a.symbol}-${i}`);
}
const sevGlyph = (s: string): string => (s === 'alert' ? '●' : s === 'watch' ? '◐' : '○');

function openSymbol(sym: string) { router.push({ path: '/markets/indices-funds', query: { sym } }); }
function askNoetica() {
  cockpit.askAbout(`Review my portfolio: ${rows.value.length} positions, equity ${money(equity.value)}, unrealized ${signed(unrealized.value)}, realized ${signed(portfolio.realized)}. Where's my concentration and risk, and what would you rebalance?`);
}

onMounted(() => cockpit.setContext({
  surface: 'Portfolio',
  entityLabel: `${rows.value.length} positions`,
  detail: `${money(equity.value)} equity · ${signed(totalPnl.value)} P&L`,
  route: '/capability/portfolios',
}));
</script>

<style scoped>
.pf { height: 100%; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 0.8rem; padding: 0.85rem 1rem 1.5rem; background: var(--bg); color: var(--text); }
.pf-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.pf-title { display: flex; align-items: baseline; gap: 0.6rem; } .pf-title h1 { margin: 0; font-size: 1.3rem; letter-spacing: -0.01em; }
.pf-eyebrow { margin: 0 0 0.1rem; font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-3); }
.pf-pill { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent); background: var(--accent-soft); border-radius: 5px; padding: 0.1rem 0.35rem; }
.pf-actions { display: flex; gap: 0.5rem; }
.pf-ask { border: 1px solid rgba(120, 160, 255, 0.45); background: rgba(120, 160, 255, 0.08); color: #93b4ff; border-radius: 8px; padding: 0.35rem 0.7rem; font-size: 0.76rem; cursor: pointer; } .pf-ask:hover { background: rgba(120, 160, 255, 0.16); color: #fff; }
.pf-reset { border: 1px solid var(--line-2); background: transparent; color: var(--text-3); border-radius: 8px; padding: 0.35rem 0.7rem; font-size: 0.76rem; cursor: pointer; } .pf-reset:hover { color: var(--text); border-color: var(--line-2); }
.pf-agent-btn { border: 1px solid rgba(110, 231, 183, 0.45); background: rgba(16, 185, 129, 0.1); color: #6ee7b7; border-radius: 8px; padding: 0.35rem 0.7rem; font-size: 0.76rem; font-weight: 600; cursor: pointer; } .pf-agent-btn:hover { background: rgba(16, 185, 129, 0.2); color: #fff; }

/* Agent panel — deterministic, proof-carrying findings + stageable orders */
.pf-agent { border: 1px solid rgba(110, 231, 183, 0.3); border-radius: 12px; background: var(--surface); padding: 0.7rem 0.85rem; display: flex; flex-direction: column; gap: 0.6rem; }
.pf-agent-bar { display: flex; gap: 0.5rem; align-items: center; }
.pf-agent-goal { flex: 1; min-width: 0; border: 1px solid var(--line-2); background: var(--surface-2, rgba(255,255,255,0.02)); color: var(--text); border-radius: 8px; padding: 0.4rem 0.6rem; font-size: 0.82rem; }
.pf-agent-goal:focus { outline: none; border-color: rgba(110, 231, 183, 0.5); }
.pf-agent-run { border: 1px solid rgba(110, 231, 183, 0.45); background: rgba(16, 185, 129, 0.14); color: #6ee7b7; border-radius: 8px; padding: 0.4rem 0.9rem; font-size: 0.78rem; font-weight: 600; cursor: pointer; } .pf-agent-run:hover { background: rgba(16, 185, 129, 0.24); }
.pf-agent-x { border: none; background: transparent; color: var(--text-3); font-size: 1.1rem; line-height: 1; cursor: pointer; padding: 0 0.3rem; } .pf-agent-x:hover { color: var(--text); }
.pf-agent-narrative { margin: 0; font-size: 0.86rem; line-height: 1.55; color: var(--text); display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; }
.pf-agent-tools { margin: 0; font-size: 0.66rem; color: var(--text-3); display: flex; align-items: center; gap: 0.3rem; flex-wrap: wrap; }
.pf-tool-chip { font-family: var(--mono, ui-monospace, monospace); font-size: 0.62rem; color: var(--text-2); border: 1px solid var(--line-2); border-radius: 4px; padding: 0.02rem 0.3rem; }
.pf-tool-sep { color: var(--line-2); } .pf-tool-note { font-style: italic; }

.pf-findings { display: flex; flex-direction: column; gap: 0.4rem; }
.pf-finding { display: flex; gap: 0.55rem; align-items: flex-start; border: 1px solid var(--line-2); border-left-width: 3px; border-radius: 8px; padding: 0.5rem 0.65rem; background: var(--surface-2, rgba(255,255,255,0.015)); }
.pf-finding.info { border-left-color: var(--text-3); }
.pf-finding.watch { border-left-color: #fbbf24; }
.pf-finding.alert { border-left-color: var(--down); }
.pf-f-sev { font-size: 0.7rem; margin-top: 0.15rem; } .pf-finding.watch .pf-f-sev { color: #fbbf24; } .pf-finding.alert .pf-f-sev { color: var(--down); } .pf-finding.info .pf-f-sev { color: var(--text-3); }
.pf-f-body { min-width: 0; }
.pf-f-title { display: flex; align-items: center; gap: 0.4rem; font-size: 0.82rem; font-weight: 650; color: var(--text); flex-wrap: wrap; }
.pf-f-detail { font-size: 0.76rem; color: var(--text-2); line-height: 1.5; margin-top: 0.1rem; }

.pf-proposed { border: 1px solid var(--line-2); border-radius: 8px; overflow: hidden; }
.pf-proposed-h { padding: 0.45rem 0.65rem; font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-3); border-bottom: 1px solid var(--line-2); }
.pf-proposed-row { display: grid; grid-template-columns: 2.6rem 3.5rem auto 1fr auto; align-items: center; gap: 0.55rem; padding: 0.45rem 0.65rem; border-bottom: 1px solid var(--line); font-size: 0.76rem; }
.pf-proposed-row:last-child { border-bottom: none; }
.pf-p-sym { font-weight: 700; } .pf-p-qty { color: var(--text-2); font-variant-numeric: tabular-nums; } .pf-p-why { color: var(--text-3); font-size: 0.7rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pf-p-stage { border: 1px solid rgba(110, 231, 183, 0.45); background: rgba(16, 185, 129, 0.12); color: #6ee7b7; border-radius: 6px; padding: 0.25rem 0.7rem; font-size: 0.72rem; font-weight: 600; cursor: pointer; } .pf-p-stage:hover:not(:disabled) { background: rgba(16, 185, 129, 0.22); } .pf-p-stage:disabled { opacity: 0.6; cursor: default; border-color: var(--line-2); color: var(--text-3); background: transparent; }

.pf-summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr)); gap: 0.6rem; }
.pf-stat { display: flex; flex-direction: column; gap: 0.1rem; border: 1px solid var(--line-2); border-radius: 10px; padding: 0.55rem 0.8rem; background: var(--surface); }
.pf-s-label { display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-3); }
.pf-s-val { font-size: 1.2rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.pf-s-val.up { color: var(--up); } .pf-s-val.down { color: var(--down); } .pf-s-val.flat { color: var(--text); }
.pf-s-sub { font-size: 0.66rem; color: var(--text-3); }

.pf-body { display: grid; grid-template-columns: 1.6fr 1fr; gap: 0.8rem; min-height: 0; }
@media (max-width: 1000px) { .pf-body { grid-template-columns: 1fr; } }
.pf-panel { border: 1px solid var(--line-2); border-radius: 12px; background: var(--surface); overflow: hidden; display: flex; flex-direction: column; }
.pf-panel-h { padding: 0.6rem 0.85rem; font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-3); border-bottom: 1px solid var(--line-2); }
.pf-hint { text-transform: none; letter-spacing: 0; color: var(--text-3); }
.pf-empty { margin: 0; padding: 1rem; font-size: 0.82rem; color: var(--text-3); line-height: 1.6; } .pf-link { color: var(--accent); text-decoration: none; } .pf-link:hover { text-decoration: underline; }

.pf-table { display: flex; flex-direction: column; overflow-y: auto; }
.pf-row { display: grid; grid-template-columns: 1.4fr 3rem 4.5rem 4.5rem 5rem 7rem; align-items: center; gap: 0.5rem; padding: 0.5rem 0.85rem; border: none; border-bottom: 1px solid var(--line); background: transparent; color: inherit; text-align: left; cursor: pointer; font-size: 0.8rem; }
.pf-row:hover { background: rgba(255, 255, 255, 0.03); }
.pf-row-head { color: var(--text-3); font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.05em; cursor: default; }
.pf-row-head:hover { background: transparent; }
.pf-row .r, .pf-row-head .r { text-align: right; font-variant-numeric: tabular-nums; }
.pf-sym { display: flex; flex-direction: column; min-width: 0; } .pf-sym b { font-size: 0.82rem; } .pf-sym small { font-size: 0.66rem; color: var(--text-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pf-row .up { color: var(--up); } .pf-row .down { color: var(--down); } .pf-row .flat { color: var(--text-2); } .pf-row small { color: inherit; opacity: 0.75; }

.pf-blotter { display: flex; flex-direction: column; overflow-y: auto; }
.pf-fill { display: grid; grid-template-columns: 2.6rem 3.5rem 1fr auto auto; align-items: center; gap: 0.5rem; padding: 0.4rem 0.85rem; border-bottom: 1px solid var(--line); cursor: pointer; font-size: 0.74rem; }
.pf-fill:hover { background: rgba(255, 255, 255, 0.03); }
.pf-fill-side { font-weight: 800; font-size: 0.62rem; border-radius: 4px; padding: 0.05rem 0.3rem; text-align: center; } .pf-fill-side.buy { color: var(--up); background: rgba(75, 191, 115, 0.14); } .pf-fill-side.sell { color: var(--down); background: rgba(240, 101, 106, 0.14); }
.pf-fill-sym { font-weight: 700; } .pf-fill-qty { color: var(--text-2); font-variant-numeric: tabular-nums; } .pf-fill-src { color: var(--text-3); font-size: 0.66rem; } .pf-fill-ts { color: var(--text-3); font-size: 0.66rem; }
.pf-prov { margin: 0; padding: 0.6rem 0.85rem; font-size: 0.66rem; color: var(--text-3); line-height: 1.5; border-top: 1px solid var(--line); }
</style>
