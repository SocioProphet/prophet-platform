<template>
  <section class="dt" aria-label="Digital twin simulation">
    <SurfaceHeader title='Digital Twin' eyebrow="Maps &amp; Analytics">
      <template #badge><span class="dt-pill">fixture</span></template>
      <template #actions>
        <div class="dt-controls">
        <label class="dt-ctl"><span>Corporate twin</span>
        <select v-model="twinId">
        <option v-for="t in twins" :key="t.id" :value="t.id">{{ t.name }}</option>
        </select>
        </label>
        <label class="dt-ctl"><span>Scenario</span>
        <select v-model="scenarioId">
        <option v-for="s in scenarios" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        </label>
        <button class="dt-ask" type="button" @click="askNoetica" title="Ask Noetica about this twin">◇ Ask Noetica</button>
        </div>
      </template>
    </SurfaceHeader>

    <p class="dt-note">{{ twin?.note }}</p>
    <p v-if="scenario && scenario.id !== 'baseline'" class="dt-scn">Scenario · {{ scenario.note }}</p>

    <div class="dt-metrics">
      <div class="dt-metric" :class="{ risk: result.valueAtRisk > 0 }">
        <span class="dt-m-label">Value at risk <ProvenanceBadge :p="riskProv" compact /></span>
        <span class="dt-m-val">{{ money(result.valueAtRisk) }}</span>
        <span class="dt-m-sub">{{ (result.valueAtRiskPct * 100).toFixed(1) }}% of EV</span>
      </div>
      <div class="dt-metric">
        <span class="dt-m-label">Path risk</span>
        <span class="dt-m-val">{{ Math.round(result.pathRiskBefore * 100) }} → <b :style="{ color: ratingColor(result.ratingAfter) }">{{ Math.round(result.pathRiskAfter * 100) }}</b></span>
        <span class="dt-m-sub">{{ result.ratingBefore }} → {{ result.ratingAfter }}</span>
      </div>
      <div class="dt-metric">
        <span class="dt-m-label">Lead time</span>
        <span class="dt-m-val">{{ result.leadTimeBefore }} → <b>{{ result.leadTimeAfter }}</b> d</span>
        <span v-if="result.leadTimeAfter > result.leadTimeBefore" class="dt-m-sub up">+{{ result.leadTimeAfter - result.leadTimeBefore }} days</span>
        <span v-else class="dt-m-sub">no change</span>
      </div>
      <div class="dt-metric">
        <span class="dt-m-label">Facilities impacted</span>
        <span class="dt-m-val">{{ result.impacted.length }} / {{ result.nodes.length }}</span>
        <span class="dt-m-sub">{{ twin?.chains.length }} chain(s) · {{ mappable.length }} geo-located</span>
      </div>
    </div>

    <div class="dt-trace"><span class="dt-trace-h">Trace across</span><CrossLinks :links="twinLinks" /></div>

    <SplitPane storage-key="digital-twin" label="graph" :initial="380">
      <template #list>
      <div class="dt-left">
        <div class="dt-graphpanel">
          <div class="dt-map-h">
            <span>Twin graph <span class="dt-hint">supply network — nodes colored by simulated impact, arrows show flow</span></span>
          </div>
          <svg class="dt-graph" :viewBox="`0 0 ${twinGraph.w} ${twinGraph.h}`" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Twin supply network graph">
            <defs>
              <marker id="dt-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M0 0 L10 5 L0 10 z" fill="rgba(255,255,255,0.28)" />
              </marker>
            </defs>
            <line
              v-for="(e, i) in twinGraph.edges"
              :key="'e' + i"
              :x1="e.x1" :y1="e.y1" :x2="e.x2" :y2="e.y2"
              :class="{ hot: e.from === selectedId || e.to === selectedId }"
              class="dt-gedge"
              marker-end="url(#dt-arrow)"
            />
            <g
              v-for="n in twinGraph.nodes"
              :key="n.id"
              class="dt-gnode"
              :class="{ sel: n.id === selectedId }"
              @click="selectedId = n.id"
            >
              <title>{{ n.name }}{{ n.sev > 0 ? ` · impact ${Math.round(n.sev * 100)}` : '' }}</title>
              <circle :cx="n.px" :cy="n.py" :r="n.id === selectedId ? 8 : 6" :fill="nodeColor(n.sev)" :stroke="n.id === selectedId ? '#58a6ff' : 'rgba(0,0,0,0.45)'" :stroke-width="n.id === selectedId ? 2.5 : 1" />
              <text :x="n.px" :y="n.py + 15" text-anchor="middle" class="dt-glabel">{{ shortName(n.name) }}</text>
            </g>
          </svg>
        </div>

        <div class="dt-mappanel">
          <div class="dt-map-h">
            <span>Twin footprint <span class="dt-hint">facilities · logistics · supply chain across geography · pins colored by simulated impact</span></span>
          </div>
          <div ref="mapEl" class="dt-map" role="img" aria-label="Corporate twin facilities plotted on an OpenStreetMap basemap"></div>
          <p v-if="mappable.length === 0" class="dt-empty">No geocoded nodes for this twin.</p>
        </div>
      </div>
      </template>

      <template #detail>

      <div class="dt-panel">
        <div class="dt-panel-h">Impact propagation</div>
        <p v-if="result.impacted.length === 0" class="dt-empty">No shock. Pick a scenario to disrupt a node and propagate it through the chain.</p>
        <div v-else class="dt-imp">
          <div
            v-for="n in result.impacted"
            :key="n.id"
            class="dt-imp-row"
            :class="{ on: n.id === selectedId }"
            @click="selectedId = n.id"
          >
            <span class="dt-imp-dot" :style="{ background: severityColor(n.severity) }" />
            <span class="dt-imp-name">{{ n.name }}</span>
            <span class="dt-imp-bar"><span class="dt-imp-fill" :style="{ width: Math.round(n.severity * 100) + '%', background: severityColor(n.severity) }" /></span>
            <span class="dt-imp-sev">{{ Math.round(n.severity * 100) }}</span>
          </div>
        </div>
        <p class="dt-prov">{{ result.provenance.note }}</p>
      </div>
      </template>
    </SplitPane>
  </section>
</template>

<script setup lang="ts">
import SurfaceHeader from '../components/SurfaceHeader.vue';
import SplitPane from '../components/SplitPane.vue';
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useRoute } from 'vue-router';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { edgesForChain, nodeById, type SCNode } from '../data/supplyChainFixture';
import { ratingColor } from '../data/supplyChainRiskFixture';
import { twins, scenarios, simulate, severityColor } from '../data/twinFixture';
import ProvenanceBadge from '../components/ProvenanceBadge.vue';
import { prov } from '../features/provenance/types';
import { useCockpit } from '../stores/cockpit';
import CrossLinks from '../components/CrossLinks.vue';
import { crossLinksForChain } from '../features/crosslink/entityLinks';

const route = useRoute();
const twinId = ref<string>('nvda');
const scenarioId = ref<string>('taiwan-fab-outage');
const selectedId = ref<string>('');

// Deep-link support: ?twin=<id> or ?chain=<supply-chain id> preselects the twin
// (the "Digital Twin" links on the Supply Chain / Land Resources surfaces).
const qTwin = typeof route.query.twin === 'string' ? route.query.twin : '';
const qChain = typeof route.query.chain === 'string' ? route.query.chain : '';
if (qTwin && twins.some((t) => t.id === qTwin)) twinId.value = qTwin;
else if (qChain) { const m = twins.find((t) => t.chains.includes(qChain)); if (m) twinId.value = m.id; }

const twin = computed(() => twins.find((t) => t.id === twinId.value));
const scenario = computed(() => scenarios.find((s) => s.id === scenarioId.value));
const result = computed(() => simulate(twinId.value, scenarioId.value));
const mappable = computed<SCNode[]>(() => result.value.nodes.filter((n) => n.geo));

// The impact metrics are simulated (deterministic shock propagation) — computed & replayable.
// Deterministic shock-propagation math, but over a fixture twin/graph — so the
// result is 'fixture'/unassayed, not 'verified' (mirrors the MapPage site-score fix).
const riskProv = computed(() => prov('fixture', {
  verifier: 'twin simulator',
  formula: 'shock propagation over supply graph → Σ severity·node-value',
  sources: ['illustrative twin (sample data)', 'supply-chain graph fixture'],
  note: result.value.provenance?.note ?? 'Deterministic simulation, but over an illustrative twin — inputs are sample data, not a live feed.',
}));

const cockpit = useCockpit();
const twinLinks = computed(() => crossLinksForChain(twin.value?.headlineSymbol));

// ── Twin graph — the supply network as a node-link diagram, laid out left→right
// by supply-chain depth, nodes colored by simulated impact, arrows showing flow.
const GW = 340;
const GH = 200;
const GPADX = 30;
const GPADY = 24;
const twinGraph = computed(() => {
  const nodes = result.value.nodes;
  const ids = new Set(nodes.map((n) => n.id));
  const chainEdges = (twin.value?.chains ?? []).flatMap((c) => edgesForChain(c));
  // Dedup + keep only edges whose endpoints are in this twin.
  const seen = new Set<string>();
  const edges = chainEdges.filter((e) => {
    const key = `${e.from}|${e.to}`;
    if (!ids.has(e.from) || !ids.has(e.to) || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  // Longest-path depth (bounded relaxation) → column per node.
  const depth = new Map<string, number>();
  nodes.forEach((n) => depth.set(n.id, 0));
  for (let iter = 0; iter < nodes.length; iter += 1) {
    let changed = false;
    for (const e of edges) {
      const d = (depth.get(e.from) ?? 0) + 1;
      if (d > (depth.get(e.to) ?? 0)) { depth.set(e.to, d); changed = true; }
    }
    if (!changed) break;
  }
  const maxDepth = Math.max(0, ...depth.values());
  const cols = new Map<number, string[]>();
  nodes.forEach((n) => { const d = depth.get(n.id) ?? 0; const a = cols.get(d) ?? []; a.push(n.id); cols.set(d, a); });
  const gx = (x: number) => GPADX + (x / 100) * (GW - 2 * GPADX);
  const gy = (y: number) => GPADY + (y / 100) * (GH - 2 * GPADY);
  const pos = new Map<string, { px: number; py: number }>();
  cols.forEach((col, d) => {
    col.forEach((id, i) => {
      const x = maxDepth ? (d / maxDepth) * 100 : 50;
      const y = col.length === 1 ? 50 : (i / (col.length - 1)) * 100;
      pos.set(id, { px: gx(x), py: gy(y) });
    });
  });
  const sev = result.value.severityById;
  const gnodes = nodes.map((n) => ({ id: n.id, name: n.name, ...pos.get(n.id)!, sev: sev[n.id] ?? 0 }));
  const gedges = edges.map((e) => {
    const a = pos.get(e.from)!; const b = pos.get(e.to)!;
    return { from: e.from, to: e.to, x1: a.px, y1: a.py, x2: b.px, y2: b.py };
  });
  return { nodes: gnodes, edges: gedges, w: GW, h: GH };
});
function nodeColor(sev: number): string { return sev > 0.001 ? severityColor(sev) : '#39404d'; }
function shortName(name: string): string { return name.length > 16 ? `${name.slice(0, 15)}…` : name; }

const money = (n: number): string =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(n);

// Assistant context + one-tap ask (defined after money() to avoid a TDZ in the immediate watch).
function askNoetica() {
  const t = twin.value; const s = scenario.value; const r = result.value;
  if (!t) return;
  cockpit.askAbout(`Read the ${t.name} digital twin under "${s?.name}": ${r.impacted.length} of ${r.nodes.length} facilities impacted, value-at-risk ${money(r.valueAtRisk)} (${(r.valueAtRiskPct * 100).toFixed(1)}% of EV). Where's the concentration and what should I hedge? Note: the twin's facilities and values are illustrative sample data for a demo, not a live model — reason about the concentration/hedging logic, not the specific figures as fact.`);
}
watch([twin, scenario], () => cockpit.setContext({
  surface: 'Digital Twin',
  entityLabel: twin.value?.name ?? 'twin',
  detail: `${scenario.value?.name} · VaR ${money(result.value.valueAtRisk)}`,
  route: '/analytics/digital-twin',
}), { immediate: true });

// ── OSM map — the twin's nodes across geography, pins colored by simulated impact.
const mapEl = ref<HTMLElement | null>(null);
let map: maplibregl.Map | null = null;
const markersById: Record<string, maplibregl.Marker> = {};

type RouteFeature = { type: 'Feature'; properties: Record<string, never>; geometry: { type: 'LineString'; coordinates: number[][] } };
type GeoJSONData = Parameters<maplibregl.GeoJSONSource['setData']>[0];

function routeData(): { type: 'FeatureCollection'; features: RouteFeature[] } {
  const chains = twin.value?.chains ?? [];
  const features = chains.flatMap((c) => edgesForChain(c)).flatMap((e): RouteFeature[] => {
    const a = nodeById(e.from)?.geo;
    const b = nodeById(e.to)?.geo;
    if (!a || !b) return [];
    return [{ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [[a.lon, a.lat], [b.lon, b.lat]] } }];
  });
  return { type: 'FeatureCollection', features };
}

function clearMarkers(): void {
  Object.values(markersById).forEach((m) => m.remove());
  for (const k of Object.keys(markersById)) delete markersById[k];
}

function render(): void {
  if (!map) return;
  const data = routeData() as unknown as GeoJSONData;
  const src = map.getSource('twin-routes') as maplibregl.GeoJSONSource | undefined;
  if (src) src.setData(data);
  else {
    map.addSource('twin-routes', { type: 'geojson', data });
    map.addLayer({ id: 'twin-routes-line', type: 'line', source: 'twin-routes', paint: { 'line-color': '#4aa3ff', 'line-width': 2, 'line-dasharray': [2, 1.5] } });
  }
  clearMarkers();
  const sev = result.value.severityById;
  const bounds = new maplibregl.LngLatBounds();
  for (const n of mappable.value) {
    const el = document.createElement('button');
    el.className = 'dt-mk' + (n.id === selectedId.value ? ' sel' : '');
    el.style.setProperty('--mk', severityColor(sev[n.id] ?? 0));
    el.setAttribute('aria-label', n.name);
    el.addEventListener('click', () => { selectedId.value = n.id; });
    const s = Math.round((sev[n.id] ?? 0) * 100);
    const m = new maplibregl.Marker({ element: el })
      .setLngLat([n.geo!.lon, n.geo!.lat])
      .setPopup(new maplibregl.Popup({ offset: 14 }).setText(`${n.name} · ${n.geo!.place}, ${n.geo!.country}${s ? ` · impact ${s}` : ''}`))
      .addTo(map);
    markersById[n.id] = m;
    bounds.extend([n.geo!.lon, n.geo!.lat]);
  }
  if (mappable.value.length && !bounds.isEmpty()) map.fitBounds(bounds, { padding: 56, maxZoom: 6, duration: 500 });
}

function initMap(): void {
  if (!mapEl.value || map) return;
  map = new maplibregl.Map({
    container: mapEl.value,
    center: [0, 20],
    zoom: 1.2,
    style: {
      version: 8,
      sources: { osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap contributors' } },
      layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
    },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  map.on('load', render);
}

onMounted(async () => { await nextTick(); initMap(); });
onUnmounted(() => { clearMarkers(); map?.remove(); map = null; });

watch([twinId, scenarioId], () => { if (map) render(); });
watch(selectedId, (id) => {
  for (const [nid, m] of Object.entries(markersById)) m.getElement().classList.toggle('sel', nid === id);
  const g = nodeById(id)?.geo;
  if (map && g) map.flyTo({ center: [g.lon, g.lat], zoom: Math.max(map.getZoom(), 4), duration: 600 });
});
</script>

<style scoped>
.dt { height: 100%; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 0.7rem; padding: 0.85rem 1rem 1.5rem; background: var(--bg); color: var(--text); }
.dt-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.dt-title { display: flex; align-items: baseline; gap: 0.6rem; } .dt-title h1 { margin: 0; font-size: 1.3rem; letter-spacing: -0.01em; color: var(--text); }
.dt-eyebrow { margin: 0 0 0.1rem; font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-3); }
.dt-pill { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent); background: var(--accent-soft); border-radius: 5px; padding: 0.1rem 0.35rem; }
.dt-controls { display: flex; gap: 0.7rem; flex-wrap: wrap; }
.dt-ctl { display: flex; flex-direction: column; gap: 0.2rem; font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-3); }
.dt-ctl select { font-size: 0.82rem; text-transform: none; letter-spacing: 0; color: var(--text); background: var(--surface); border: 1px solid var(--line-2); border-radius: 8px; padding: 0.35rem 0.5rem; min-width: 12rem; }
.dt-ask { align-self: flex-end; border: 1px solid rgba(120, 160, 255, 0.45); background: rgba(120, 160, 255, 0.08); color: #93b4ff; border-radius: 8px; padding: 0.4rem 0.7rem; font-size: 0.76rem; cursor: pointer; } .dt-ask:hover { background: rgba(120, 160, 255, 0.16); color: #fff; }
.dt-trace { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; } .dt-trace-h { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3); }
.dt-note { margin: 0; font-size: 0.82rem; color: var(--text-2); max-width: 80ch; }
.dt-scn { margin: 0; font-size: 0.78rem; color: var(--text-3); max-width: 80ch; }

.dt-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr)); gap: 0.6rem; }
.dt-metric { display: flex; flex-direction: column; gap: 0.1rem; border: 1px solid var(--line-2); border-radius: 10px; padding: 0.5rem 0.75rem; background: var(--surface); }
.dt-metric.risk { border-color: rgba(240, 101, 106, 0.4); }
.dt-m-label { display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-3); }
.dt-m-val { font-size: 1.05rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.dt-m-sub { font-size: 0.66rem; color: var(--text-3); } .dt-m-sub.up { color: var(--down); }

.dt-body { display: grid; grid-template-columns: 1.5fr 1fr; gap: 0.8rem; }
@media (max-width: 1000px) { .dt-body { grid-template-columns: 1fr; } }
.dt-left { display: flex; flex-direction: column; gap: 0.8rem; min-width: 0; }
.dt-graphpanel { border: 1px solid var(--line-2); border-radius: 12px; overflow: hidden; background: var(--surface); }
.dt-graph { display: block; width: 100%; height: 300px; background: linear-gradient(180deg, rgba(255,255,255,0.015), transparent); }
.dt-gedge { stroke: rgba(255, 255, 255, 0.16); stroke-width: 1.2; transition: stroke 0.15s ease; }
.dt-gedge.hot { stroke: rgba(88, 166, 255, 0.7); stroke-width: 1.8; }
.dt-gnode { cursor: pointer; }
.dt-gnode circle { transition: r 0.12s ease; }
.dt-gnode:hover circle { r: 8; }
.dt-glabel { font-size: 7px; fill: var(--text-2); pointer-events: none; }
.dt-gnode.sel .dt-glabel { fill: var(--text); font-weight: 700; }
.dt-mappanel { border: 1px solid var(--line-2); border-radius: 12px; overflow: hidden; background: var(--surface); }
.dt-map-h { padding: 0.55rem 0.8rem; font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-3); border-bottom: 1px solid var(--line-2); }
.dt-hint { text-transform: none; letter-spacing: 0; color: var(--text-3); font-size: 0.66rem; }
.dt-map { height: 340px; width: 100%; }
.dt-panel { border: 1px solid var(--line-2); border-radius: 12px; padding: 0.7rem 0.85rem; background: var(--surface); }
.dt-panel-h { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-3); margin-bottom: 0.6rem; }
.dt-imp { display: flex; flex-direction: column; gap: 0.35rem; }
.dt-imp-row { display: grid; grid-template-columns: auto 1fr 3rem 1.6rem; align-items: center; gap: 0.5rem; padding: 0.25rem 0.35rem; border-radius: 7px; cursor: pointer; }
.dt-imp-row:hover, .dt-imp-row.on { background: var(--surface-2); }
.dt-imp-dot { width: 9px; height: 9px; border-radius: 50%; }
.dt-imp-name { font-size: 0.78rem; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dt-imp-bar { height: 6px; border-radius: 3px; background: rgba(255,255,255,0.06); overflow: hidden; }
.dt-imp-fill { display: block; height: 100%; border-radius: 3px; }
.dt-imp-sev { font-size: 0.74rem; font-weight: 700; text-align: right; font-variant-numeric: tabular-nums; color: var(--text-2); }
.dt-empty { margin: 0; font-size: 0.8rem; color: var(--text-3); }
.dt-prov { margin: 0.7rem 0 0; font-size: 0.66rem; color: var(--text-3); line-height: 1.5; border-top: 1px solid var(--line); padding-top: 0.6rem; }
</style>

<style>
.dt-mk { width: 15px; height: 15px; border-radius: 50%; border: 2px solid #fff; background: var(--mk, #4bbf73); box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.35); cursor: pointer; padding: 0; transition: transform 0.15s ease, box-shadow 0.15s ease; }
.dt-mk:hover { transform: scale(1.25); }
.dt-mk.sel { width: 19px; height: 19px; box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.9); }
</style>
