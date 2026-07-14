<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type Loc = {
  id: string; suburb: string; state: string; lat: number; lng: number
  format: string; ownership: string; metro_tier: number; catchment_profile: string
  est_annual_sales_aud: number; modeled_weekly_footfall: number; basis: string
}
type LocationsPayload = {
  subject: string
  locations: Loc[]
  sample_size: number
  network_totals: { total_au_restaurants: number; drive_thru: number; strip: number; other: number; as_of: string }
  org_twin: {
    sample_modeled_annual_sales_aud: number
    sample_modeled_weekly_footfall: number
    by_state: Record<string, number>
    by_format: Record<string, number>
    network_extrapolation_note: string
  }
}

const data = ref<LocationsPayload | null>(null)
const loading = ref(false)
const error = ref('')
const q = ref('')
const selected = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/bff/v1/locations?company=gyg&q=${encodeURIComponent(q.value)}`)
    if (!res.ok) throw new Error(`request failed: ${res.status}`)
    data.value = await res.json()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'request failed'
  } finally {
    loading.value = false
  }
}
onMounted(load)

function money(n: number): string {
  return n >= 1e9 ? `A$${(n / 1e9).toFixed(2)}B` : `A$${(n / 1e6).toFixed(1)}M`
}

// project lat/lng -> SVG (Australia bounds)
const LNG0 = 112.5, LNG1 = 154, LAT_TOP = -10, LAT_BOT = -44, W = 440, H = 360
function px(lng: number) { return ((lng - LNG0) / (LNG1 - LNG0)) * W }
function py(lat: number) { return ((LAT_TOP - lat) / (LAT_TOP - LAT_BOT)) * H }

const AU_OUTLINE: number[][] = [
  [142.5,-10.7],[145.5,-16],[149,-21],[153,-25],[153.5,-28.2],[151,-33.9],[150,-37.5],
  [146,-38.9],[141,-38.4],[139,-35.5],[135,-34.8],[132,-32],[129,-31.7],[126,-32.3],
  [123,-33.9],[118,-35],[115,-34.5],[114,-28],[113.5,-24],[114,-22],[116,-20.5],
  [121,-19.5],[123,-16.5],[126,-14],[129,-15],[130.5,-12],[132,-11.5],[135,-12],
  [137,-16],[140,-17.5],[141,-16],[141.5,-13],[142.5,-10.7],
]
const outlinePoints = computed(() => AU_OUTLINE.map(([lng, lat]) => `${px(lng).toFixed(1)},${py(lat).toFixed(1)}`).join(' '))

const FORMAT_COLOR: Record<string, string> = { drive_thru: '#10b981', strip: '#3b82f6', shopping_centre: '#f59e0b' }
function dotColor(f: string) { return FORMAT_COLOR[f] ?? '#64748b' }
function dotR(footfall: number) { return 3 + Math.sqrt(footfall) / 22 }

const selectedLoc = computed(() => data.value?.locations.find((l) => l.id === selected.value) ?? null)
</script>

<template>
  <section style="border:1px solid #cbd5e1;border-radius:16px;padding:1rem;margin-top:1.5rem;background:#f8fafc;">
    <div style="display:flex;gap:.75rem;align-items:flex-start;justify-content:space-between;">
      <div>
        <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.65;font-weight:700;">Location intelligence · org digital twin</div>
        <h2 style="margin:.4rem 0 .35rem 0;font-size:1.35rem;font-weight:750;">{{ data?.subject ?? 'Guzman y Gomez' }} — network map</h2>
        <p style="margin:0;opacity:.78;max-width:820px;">Search and plot restaurants, with a <strong>modeled</strong> per-site foot-traffic and sales estimate (anchored to disclosed format AUV, not measured footfall).</p>
      </div>
    </div>

    <p v-if="error" style="border:1px solid #fecaca;background:#fef2f2;border-radius:10px;padding:.75rem;margin:1rem 0 0 0;color:#991b1b;">{{ error }}</p>

    <div v-if="data" style="margin-top:1rem;">
      <div style="display:flex;gap:.5rem;margin-bottom:.75rem;">
        <input v-model="q" @keyup.enter="load" placeholder="Search suburb, state, or format (e.g. coast, VIC, drive_thru)"
          style="flex:1;padding:.45rem .7rem;border:1px solid #cbd5e1;border-radius:8px;" />
        <button @click="load" style="padding:.45rem .8rem;border:1px solid #94a3b8;border-radius:8px;background:white;">{{ loading ? '…' : 'Search' }}</button>
      </div>

      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem;">
        <!-- Map -->
        <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.4rem;">
            <h3 style="margin:0;font-size:1rem;">Map ({{ data.sample_size }} of {{ data.network_totals.total_au_restaurants }})</h3>
            <div style="font-size:.72rem;display:flex;gap:.6rem;">
              <span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#10b981;"></span> drive-thru</span>
              <span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#3b82f6;"></span> strip</span>
              <span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#f59e0b;"></span> centre</span>
            </div>
          </div>
          <svg :viewBox="`0 0 ${W} ${H}`" style="width:100%;height:auto;">
            <polygon :points="outlinePoints" fill="#eef2f7" stroke="#cbd5e1" stroke-width="1" />
            <g v-for="l in data.locations" :key="l.id">
              <circle :cx="px(l.lng)" :cy="py(l.lat)" :r="dotR(l.modeled_weekly_footfall)"
                :fill="dotColor(l.format)" :fill-opacity="selected===l.id ? 1 : 0.7"
                :stroke="selected===l.id ? '#0f172a' : 'white'" :stroke-width="selected===l.id ? 2 : 1"
                style="cursor:pointer" @click="selected = l.id" />
            </g>
          </svg>
          <p style="margin:.4rem 0 0 0;font-size:.72rem;opacity:.55;">Dot size ∝ modeled weekly footfall. Click a dot for detail. Coordinates approximate.</p>
        </article>

        <!-- Org twin rollup -->
        <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
          <h3 style="margin:0 0 .5rem 0;font-size:1rem;">Org digital twin (sample rollup)</h3>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem;">
            <div><div style="font-size:.72rem;opacity:.6;">Modeled annual sales</div><div style="font-size:1.2rem;font-weight:700;">{{ money(data.org_twin.sample_modeled_annual_sales_aud) }}</div></div>
            <div><div style="font-size:.72rem;opacity:.6;">Modeled weekly footfall</div><div style="font-size:1.2rem;font-weight:700;">{{ data.org_twin.sample_modeled_weekly_footfall.toLocaleString() }}</div></div>
          </div>
          <h4 style="margin:.75rem 0 .3rem 0;font-size:.85rem;">By state</h4>
          <div style="display:flex;flex-wrap:wrap;gap:.35rem;">
            <span v-for="(n,s) in data.org_twin.by_state" :key="s" style="font-size:.78rem;padding:.15rem .5rem;border:1px solid #e2e8f0;border-radius:999px;">{{ s }} · {{ n }}</span>
          </div>
          <p style="margin:.75rem 0 0 0;font-size:.76rem;opacity:.6;">{{ data.org_twin.network_extrapolation_note }}</p>
        </article>
      </div>

      <!-- Selected location detail -->
      <article v-if="selectedLoc" style="border:1px solid #a7f3d0;background:#ecfdf5;border-radius:12px;padding:.85rem;margin-top:1rem;">
        <div style="display:flex;justify-content:space-between;align-items:baseline;">
          <h3 style="margin:0;font-size:1.05rem;">{{ selectedLoc.suburb }} <span style="font-size:.8rem;opacity:.6;">· {{ selectedLoc.state }} · {{ selectedLoc.format.replace('_',' ') }} · {{ selectedLoc.ownership }}</span></h3>
          <button @click="selected = null" style="border:none;background:none;cursor:pointer;font-size:1rem;opacity:.5;">✕</button>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem;margin-top:.5rem;">
          <div><div style="font-size:.72rem;opacity:.6;">Modeled annual sales</div><div style="font-size:1.1rem;font-weight:700;">{{ money(selectedLoc.est_annual_sales_aud) }}</div></div>
          <div><div style="font-size:.72rem;opacity:.6;">Modeled weekly footfall</div><div style="font-size:1.1rem;font-weight:700;">{{ selectedLoc.modeled_weekly_footfall.toLocaleString() }}</div></div>
          <div><div style="font-size:.72rem;opacity:.6;">Catchment</div><div style="font-size:.9rem;">{{ selectedLoc.catchment_profile }}</div></div>
        </div>
        <p style="margin:.6rem 0 0 0;font-size:.74rem;opacity:.6;">Basis: {{ selectedLoc.basis }}</p>
      </article>
    </div>
  </section>
</template>
