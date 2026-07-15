<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type GraphNode = { id: string; labels: string[]; properties: Record<string, any> }
type GraphEdge = { label: string; from: string; to: string; properties: Record<string, any> }

type EditableAssumption = { kpi: string; driver: string; domain: string; delta_pct: number; polarity: string }

type CausalValuation = {
  company: string
  subject: string
  recomputed: boolean
  assumptions_editable: EditableAssumption[]
  valuation: {
    currency: string
    ev_baseline: number
    projected_ev: number
    value_uplift: number
    uplift_fraction: number
  }
  timeseries: {
    horizon_years: number
    discount_rate: number
    periods: Array<{ year: number; projected_enterprise_value: number; total_value_uplift: number; value_uplift_fraction: number; incremental_value_uplift: number }>
    terminal_projected_enterprise_value: number
    terminal_total_value_uplift: number
    present_value_of_uplift: number
  }
  causal_graph: { nodes: GraphNode[]; edges: GraphEdge[] }
  vdt: {
    scenario: string
    industry: string
    per_driver_uplift: Record<string, number>
    per_kpi_contribution: Array<{ kpi: string; driver: string; domain: string; delta_pct: number; polarity: string; value_contribution: number }>
    epistemic_status: Record<string, any>
    assumptions: string[]
    limitations: string[]
    evidence_refs: string[]
  }
  provenance: Record<string, any>
  headline: string
}

const data = ref<CausalValuation | null>(null)
const loading = ref(false)
const error = ref('')
const dirty = ref(false)
// user assumption overrides: kpi name -> delta_pct
const overrides = ref<Record<string, number>>({})
const horizon = ref(5)
const discountPct = ref(9)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/bff/v1/valuation/causal?company=gyg')
    if (!res.ok) throw new Error(`request failed: ${res.status}`)
    data.value = await res.json()
    overrides.value = Object.fromEntries((data.value?.assumptions_editable ?? []).map((a) => [a.kpi, a.delta_pct]))
    horizon.value = data.value?.timeseries.horizon_years ?? 5
    discountPct.value = Math.round((data.value?.timeseries.discount_rate ?? 0.09) * 100)
    dirty.value = false
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'request failed'
    data.value = null
  } finally {
    loading.value = false
  }
}

async function recompute() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/bff/v1/valuation/causal/recompute?company=gyg', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ kpi_overrides: overrides.value, horizon_years: horizon.value, discount_rate: discountPct.value / 100 }),
    })
    if (!res.ok) throw new Error(`recompute failed: ${res.status}`)
    data.value = await res.json()
    dirty.value = false
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'recompute failed'
  } finally {
    loading.value = false
  }
}

function onSlide(kpi: string, value: string) {
  overrides.value[kpi] = Number(value)
  dirty.value = true
}

function resetAssumptions() {
  overrides.value = Object.fromEntries((data.value?.assumptions_editable ?? []).map((a) => [a.kpi, a.delta_pct]))
  dirty.value = true
  recompute()
}

const sliderBounds = (polarity: string) =>
  polarity === 'lower_better' ? { min: -20, max: 0 } : { min: 0, max: 40 }

onMounted(load)

function money(n: number, currency = 'AUD'): string {
  const abs = Math.abs(n)
  if (abs >= 1e9) return `${currency} ${(n / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `${currency} ${(n / 1e6).toFixed(1)}M`
  return `${currency} ${n.toLocaleString()}`
}

const nodeById = computed(() => {
  const m = new Map<string, GraphNode>()
  for (const n of data.value?.causal_graph.nodes ?? []) m.set(n.id, n)
  return m
})

const supplyNodes = computed(() =>
  (data.value?.causal_graph.nodes ?? []).filter((n) => n.labels.includes('SupplyChainNode'))
)

// causal edges: supply-chain node -> KPI (CAUSES / CONSTRAINS / REDUCES)
const causalEdges = computed(() =>
  (data.value?.causal_graph.edges ?? []).filter((e) => ['CAUSES', 'CONSTRAINS', 'REDUCES'].includes(e.label))
)

// KPI leaves with the driver they roll up to, sorted by contribution
const kpis = computed(() =>
  [...(data.value?.vdt.per_kpi_contribution ?? [])].sort((a, b) => b.value_contribution - a.value_contribution)
)

const drivers = computed(() =>
  Object.entries(data.value?.vdt.per_driver_uplift ?? {}).sort((a, b) => b[1] - a[1])
)

// for a supply-chain node, the KPIs it causally drives (with mechanism)
function drivenBy(nodeId: string) {
  return causalEdges.value
    .filter((e) => e.from === nodeId)
    .map((e) => ({ kpi: nodeById.value.get(e.to)?.properties?.name ?? e.to, mechanism: e.properties?.mechanism ?? '', relation: e.label }))
}

const maxContribution = computed(() => Math.max(1, ...kpis.value.map((k) => k.value_contribution)))

const periods = computed(() => data.value?.timeseries.periods ?? [])
const maxProjected = computed(() => Math.max(1, ...periods.value.map((p) => p.projected_enterprise_value)))
const minBaseline = computed(() => data.value?.valuation.ev_baseline ?? 0)
</script>

<template>
  <section style="border:1px solid #cbd5e1;border-radius:16px;padding:1rem;margin-top:1.5rem;background:#f8fafc;">
    <div style="display:flex;gap:.75rem;align-items:flex-start;justify-content:space-between;">
      <div>
        <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.65;font-weight:700;">
          Causal Valuation · Portfolio-manager persona
        </div>
        <h2 style="margin:.4rem 0 .35rem 0;font-size:1.35rem;font-weight:750;">
          {{ data?.subject ?? 'Guzman y Gomez (ASX:GYG)' }}
        </h2>
        <p style="margin:0;opacity:.78;max-width:820px;">
          Supply-chain graph → causal drivers → economic-prophet value-driver tree → enterprise value.
          Advisory measurement of a public-sourced scenario — <strong>not investment advice</strong>.
        </p>
      </div>
      <button @click="load" style="padding:.45rem .75rem;border:1px solid #94a3b8;border-radius:8px;background:white;white-space:nowrap;">
        {{ loading ? 'Loading…' : 'Reload' }}
      </button>
    </div>

    <p v-if="error" style="border:1px solid #fecaca;background:#fef2f2;border-radius:10px;padding:.75rem;margin:1rem 0 0 0;color:#991b1b;">
      {{ error }}
    </p>

    <div v-if="data" style="margin-top:1rem;display:grid;gap:1rem;">
      <!-- Valuation banner -->
      <section style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.95rem;">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:.75rem;align-items:end;">
          <div>
            <div style="font-size:.78rem;opacity:.6;text-transform:uppercase;letter-spacing:.05em;">Enterprise value (baseline)</div>
            <div style="font-size:1.4rem;font-weight:700;">{{ money(data.valuation.ev_baseline, data.valuation.currency) }}</div>
          </div>
          <div style="font-size:1.6rem;opacity:.4;text-align:center;">→</div>
          <div>
            <div style="font-size:.78rem;opacity:.6;text-transform:uppercase;letter-spacing:.05em;">Projected enterprise value</div>
            <div style="font-size:1.4rem;font-weight:700;color:#065f46;">{{ money(data.valuation.projected_ev, data.valuation.currency) }}</div>
          </div>
          <div>
            <div style="font-size:.78rem;opacity:.6;text-transform:uppercase;letter-spacing:.05em;">Scenario uplift</div>
            <div style="font-size:1.4rem;font-weight:700;color:#065f46;">
              +{{ money(data.valuation.value_uplift, data.valuation.currency) }}
              <span style="font-size:.95rem;opacity:.7;">({{ (data.valuation.uplift_fraction * 100).toFixed(2) }}%)</span>
            </div>
          </div>
        </div>
        <p style="margin:.85rem 0 0 0;opacity:.82;">{{ data.headline }}</p>
      </section>

      <!-- Interactive assumptions: re-enter the tree, recompute via the engine -->
      <section style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:.5rem;flex-wrap:wrap;">
          <h3 style="margin:0;font-size:1rem;">Scenario assumptions
            <span v-if="data.recomputed" style="font-size:.72rem;font-weight:600;color:#065f46;background:#ecfdf5;border:1px solid #a7f3d0;border-radius:999px;padding:.1rem .5rem;margin-left:.4rem;">recomputed via engine</span>
          </h3>
          <div style="display:flex;gap:.5rem;">
            <button @click="resetAssumptions" style="padding:.35rem .7rem;border:1px solid #cbd5e1;border-radius:8px;background:white;">Reset</button>
            <button @click="recompute" :disabled="!dirty || loading"
              :style="{ padding:'.35rem .8rem', borderRadius:'8px', border:'1px solid ' + (dirty ? '#10b981' : '#cbd5e1'), background: dirty ? '#10b981' : 'white', color: dirty ? 'white' : '#64748b', cursor: dirty ? 'pointer' : 'default' }">
              {{ loading ? 'Recomputing…' : 'Recompute valuation' }}
            </button>
          </div>
        </div>
        <p style="margin:.4rem 0 .75rem 0;font-size:.82rem;opacity:.65;">Move a lever and recompute — the value math runs in the economic-prophet engine, not the browser.</p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:.5rem 1.25rem;margin-bottom:.75rem;padding-bottom:.75rem;border-bottom:1px solid #eef2f7;">
          <div>
            <div style="display:flex;justify-content:space-between;font-size:.82rem;"><span><strong>Time horizon</strong></span><span style="font-weight:650;">{{ horizon }} years</span></div>
            <input type="range" min="1" max="10" step="1" :value="horizon" @input="horizon = Number(($event.target as HTMLInputElement).value); dirty = true" style="width:100%;margin-top:.25rem;" />
          </div>
          <div>
            <div style="display:flex;justify-content:space-between;font-size:.82rem;"><span><strong>Discount rate</strong></span><span style="font-weight:650;">{{ discountPct }}%</span></div>
            <input type="range" min="0" max="20" step="0.5" :value="discountPct" @input="discountPct = Number(($event.target as HTMLInputElement).value); dirty = true" style="width:100%;margin-top:.25rem;" />
          </div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:.75rem 1.25rem;">
          <div v-for="a in data.assumptions_editable" :key="a.kpi">
            <div style="display:flex;justify-content:space-between;font-size:.82rem;">
              <span><strong>{{ a.driver }}</strong> · {{ a.kpi }}</span>
              <span style="font-weight:650;">{{ overrides[a.kpi] > 0 ? '+' : '' }}{{ overrides[a.kpi] }}%</span>
            </div>
            <input type="range" :min="sliderBounds(a.polarity).min" :max="sliderBounds(a.polarity).max" step="0.5"
              :value="overrides[a.kpi]" @input="onSlide(a.kpi, ($event.target as HTMLInputElement).value)"
              style="width:100%;margin-top:.25rem;" />
            <div style="font-size:.72rem;opacity:.5;">{{ a.domain }} · {{ a.polarity }}</div>
          </div>
        </div>
      </section>

      <!-- Causal walk: supply chain -> value drivers -> valuation -->
      <section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem;">
        <!-- Stage 1: supply chain -->
        <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
          <h3 style="margin:0 0 .6rem 0;font-size:1rem;">1 · Supply-chain graph → causal levers</h3>
          <div v-for="n in supplyNodes" :key="n.id" style="border:1px solid #eef2f7;border-radius:10px;padding:.55rem;margin:.5rem 0;">
            <div style="font-weight:650;">{{ n.properties.name }}</div>
            <div v-if="n.properties.note" style="font-size:.8rem;opacity:.62;margin-top:.15rem;">{{ n.properties.note }}</div>
            <ul style="margin:.4rem 0 0 0;padding-left:1rem;">
              <li v-for="(d, i) in drivenBy(n.id)" :key="i" style="margin:.25rem 0;font-size:.85rem;">
                <code style="font-size:.75rem;background:#f1f5f9;padding:.05rem .3rem;border-radius:4px;">{{ d.relation }}</code>
                <strong> {{ d.kpi }}</strong> — {{ d.mechanism }}
              </li>
            </ul>
          </div>
        </article>

        <!-- Stage 2: KPI -> driver contributions -->
        <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
          <h3 style="margin:0 0 .6rem 0;font-size:1rem;">2 · Value-driver KPIs (engine contribution)</h3>
          <div v-for="k in kpis" :key="k.kpi" style="margin:.55rem 0;">
            <div style="display:flex;justify-content:space-between;gap:.5rem;">
              <span style="font-size:.88rem;"><strong>{{ k.driver }}</strong> · {{ k.kpi }}</span>
              <span style="font-size:.85rem;font-weight:650;color:#065f46;white-space:nowrap;">+{{ money(k.value_contribution) }}</span>
            </div>
            <div style="height:8px;background:#eef2f7;border-radius:6px;margin-top:.25rem;overflow:hidden;">
              <div :style="{ width: (k.value_contribution / maxContribution * 100) + '%', height:'100%', background:'#10b981' }"></div>
            </div>
            <div style="font-size:.74rem;opacity:.55;margin-top:.15rem;">
              {{ k.domain }} · Δ {{ k.delta_pct }}% ({{ k.polarity }})
            </div>
          </div>
        </article>

        <!-- Stage 3: driver -> valuation -->
        <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
          <h3 style="margin:0 0 .6rem 0;font-size:1rem;">3 · Driver uplift → enterprise value</h3>
          <div v-for="[name, uplift] in drivers" :key="name" style="display:flex;justify-content:space-between;gap:.5rem;margin:.5rem 0;padding:.5rem;border:1px solid #eef2f7;border-radius:10px;">
            <span style="font-weight:650;">{{ name }}</span>
            <span style="font-weight:700;color:#065f46;white-space:nowrap;">+{{ money(uplift) }}</span>
          </div>
          <div style="display:flex;justify-content:space-between;gap:.5rem;margin-top:.75rem;padding:.6rem;border-radius:10px;background:#ecfdf5;border:1px solid #a7f3d0;">
            <span style="font-weight:750;">GYG enterprise value</span>
            <span style="font-weight:800;">{{ money(data.valuation.projected_ev, data.valuation.currency) }}</span>
          </div>
        </article>
      </section>

      <!-- Time-span trajectory: multi-period projection -->
      <section style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
        <div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:.5rem;">
          <h3 style="margin:0;font-size:1rem;">Projected enterprise value over {{ data.timeseries.horizon_years }} years</h3>
          <div style="font-size:.85rem;">
            <span style="opacity:.6;">terminal</span> <strong>{{ money(data.timeseries.terminal_projected_enterprise_value) }}</strong>
            <span style="opacity:.6;margin-left:.75rem;">PV of uplift @ {{ (data.timeseries.discount_rate*100).toFixed(1) }}%</span> <strong style="color:#065f46;">{{ money(data.timeseries.present_value_of_uplift) }}</strong>
          </div>
        </div>
        <div style="display:flex;align-items:flex-end;gap:.5rem;height:130px;margin-top:1rem;">
          <div v-for="p in periods" :key="p.year" style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;">
            <div style="font-size:.72rem;font-weight:600;color:#065f46;">{{ money(p.projected_enterprise_value) }}</div>
            <div :style="{ width:'100%', maxWidth:'46px', height: ((p.projected_enterprise_value - minBaseline*0.98) / (maxProjected - minBaseline*0.98) * 100) + '%', background:'#10b981', borderRadius:'6px 6px 0 0', minHeight:'4px', marginTop:'.2rem' }"></div>
            <div style="font-size:.74rem;opacity:.6;margin-top:.25rem;">y{{ p.year }}</div>
          </div>
        </div>
        <p style="margin:.5rem 0 0 0;font-size:.76rem;opacity:.55;">Compounding levers (comparable sales, rollout, drive-thru AUV) recur each year; step levers (COGS, labour, supply resilience) are one-time improvements held flat. Present value discounts the incremental uplift stream.</p>
      </section>

      <!-- Governance: epistemic status + provenance + non-claims -->
      <section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem;">
        <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
          <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Provenance</h3>
          <div style="display:grid;gap:.35rem;font-size:.85rem;">
            <div><strong>Data</strong> — <code>{{ data.vdt.epistemic_status.level }}</code> · confidence {{ data.vdt.epistemic_status.confidence }} · {{ data.vdt.epistemic_status.review_status }}</div>
            <div><strong>Value engine</strong> — <code>{{ data.provenance.engine }}</code></div>
            <div><strong>Value source</strong> — <code style="font-size:.72rem;">{{ data.provenance.value_source }}</code></div>
            <div><strong>Graph source</strong> — <code style="font-size:.72rem;">{{ data.provenance.graph_source }}</code></div>
          </div>
          <h4 style="margin:.75rem 0 .35rem 0;font-size:.85rem;">Public sources</h4>
          <ul style="margin:0;padding-left:1rem;">
            <li v-for="ref in data.vdt.evidence_refs" :key="ref" style="margin:.2rem 0;font-size:.76rem;word-break:break-all;">
              <a v-if="ref.startsWith('http')" :href="ref" target="_blank" rel="noopener">{{ ref }}</a>
              <code v-else>{{ ref }}</code>
            </li>
          </ul>
        </article>

        <article style="border:1px solid #fde68a;border-radius:12px;background:#fffbeb;padding:.85rem;">
          <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Measurement boundary (non-claims)</h3>
          <p style="margin:0 0 .5rem 0;font-size:.82rem;">This is an advisory measurement of a scenario, not a recommendation, target price, or valuation opinion.</p>
          <ul style="margin:0;padding-left:1rem;">
            <li v-for="lim in data.vdt.limitations" :key="lim" style="margin:.3rem 0;font-size:.82rem;">{{ lim }}</li>
          </ul>
        </article>
      </section>
    </div>
  </section>
</template>
