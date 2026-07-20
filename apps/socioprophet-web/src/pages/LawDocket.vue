<template>
  <section class="lw" aria-label="Legal docket">
    <SurfaceHeader :title="scope?.label ?? 'Docket'" :eyebrow="(scope) ? (scope.domain) : ''">
      <template #badge><span class="lw-pill" :class="{ live: isLive }">{{ isLive ? `live · ${liveDockets?.length} filings` : 'fixture' }}</span></template>
      <template #search>
        <form class="term-cmd" @submit.prevent="runCmd">
        <span class="term-cmd-prompt">⌕</span>
        <input v-model="cmd" spellcheck="false" placeholder="Search cite, title, agency, #tag…" aria-label="Search dockets" />
        <button type="submit" class="term-cmd-go">&lt;GO&gt;</button>
        </form>
      </template>
      <template #actions>
        <div class="lw-filters">
        <button v-for="s in statuses" :key="s" class="lw-fbtn" :class="{ on: status === s }" @click="setStatus(s)">{{ s }}</button>
        </div>
        <LiveToggle :state="liveState" label="Go live" live-text="Federal Register" title="Pull real recent filings from the U.S. Federal Register (public, no key). Live dockets are genuinely retrieved — grounded, with real citations." @click="goLive" />
      </template>
    </SurfaceHeader>

    <SplitPane storage-key="law-docket" label="dockets" :initial="360">
      <template #list>
        <!-- Docket list -->
        <div ref="listEl" class="lw-list" aria-label="Dockets" @keydown="arrowRove($event, listEl, '.lw-row')">
        <p class="lw-count">{{ results.length }} item{{ results.length === 1 ? '' : 's' }}</p>
        <button
          v-for="d in results"
          :key="d.id"
          class="lw-row"
          :class="{ on: d.id === selectedId }"
          @click="selectedId = d.id"
        >
          <div class="lw-row-top">
            <span class="lw-treat" :class="treatmentOf(d).kind" :title="treatmentOf(d).label + ' — ' + treatmentOf(d).why">{{ treatmentOf(d).glyph }}</span>
            <span class="lw-type" :class="d.type">{{ d.type }}</span>
            <span class="lw-cite">{{ d.cite }}</span>
            <span class="lw-status" :class="d.status">{{ d.status }}</span>
          </div>
          <div class="lw-row-title">{{ d.title }}</div>
          <div class="lw-row-meta">{{ d.jurisdiction }} · updated {{ relative(d.updated) }}</div>
        </button>
        <p v-if="results.length === 0" class="lw-empty">No items in this scope.</p>
        </div>
      </template>

      <template #detail>
      <!-- Detail + redline -->
      <article v-if="selected" class="lw-detail" aria-label="Docket detail">
        <!-- provenance ribbon -->
        <div class="lw-ribbon">
          <ProvenanceBadge :p="docketProv" />
          <button class="lw-ask" type="button" @click="askNoetica" title="Ask Noetica about this docket">◇ Ask Noetica</button>
          <span class="lw-ribbon-as">as of {{ asOfLabel }}</span>
        </div>

        <div class="lw-d-kicker">
          <span class="lw-type" :class="selected.type">{{ selected.type }}</span>
          <span class="lw-status" :class="selected.status">{{ selected.status }}</span>
        </div>
        <h2 class="lw-d-title">{{ selected.title }}</h2>
        <div class="lw-d-meta">{{ selected.cite }} · {{ selected.jurisdiction }} · updated {{ relative(selected.updated) }}</div>

        <!-- Citator banner — the "can I rely on this?" verdict, up front (Shepard's/KeyCite). -->
        <div class="lw-treat-banner" :class="treatment.kind" :aria-label="`Citator: ${treatment.label}`">
          <span class="lw-tb-glyph">{{ treatment.glyph }}</span>
          <div class="lw-tb-body">
            <div class="lw-tb-label">{{ treatment.label }}<span class="lw-tb-src">citator</span></div>
            <div class="lw-tb-why">{{ treatment.why }}</div>
          </div>
          <div class="lw-tb-meta">
            <span v-if="citedBy.length">cited by <b>{{ citedBy.length }}</b></span>
            <span v-if="holmesVerdict?.evidence_count"><b>{{ holmesVerdict.evidence_count }}</b> graph facts</span>
          </div>
        </div>

        <!-- Lifecycle timeline: comment → pending → enacted → effective -->
        <div class="lw-timeline" aria-label="Docket lifecycle">
          <template v-for="(st, i) in lifecycle" :key="st.key">
            <div class="lw-tl-step" :class="st.state"><span class="lw-tl-dot" /><span class="lw-tl-lbl">{{ st.label }}</span></div>
            <div v-if="i < lifecycle.length - 1" class="lw-tl-bar" :class="{ done: st.state === 'done' }" />
          </template>
        </div>

        <!-- Metadata — inline definition row, no boxes (Tufte: type does the work). -->
        <dl class="lw-meta-line">
          <div><dt>Agency</dt><dd>{{ selected.agency }}</dd></div>
          <div><dt>Jurisdiction</dt><dd>{{ selected.jurisdiction }}</dd></div>
          <div v-if="selected.effectiveDate"><dt>Effective</dt><dd>{{ selected.effectiveDate.includes('T') ? dateLabel(selected.effectiveDate) : selected.effectiveDate }}</dd></div>
          <div v-if="selected.commentDeadline"><dt>Comment closes</dt><dd :class="{ soon: deadlineSoon(selected.commentDeadline) }">{{ dateLabel(selected.commentDeadline) }} · {{ countdown(selected.commentDeadline) }}</dd></div>
        </dl>

        <!-- Holding — the operative recommendation/ruling, stated once. -->
        <section class="lw-section">
          <div class="lw-sec-h">Holding</div>
          <p class="lw-d-summary">{{ selected.summary }}</p>
        </section>

        <!-- Who it hits — the distinct downstream / compliance read (NOT a restatement). -->
        <section class="lw-section">
          <div class="lw-sec-h">Who it hits</div>
          <p class="lw-impact">{{ selected.impact }}</p>
          <div class="lw-tags"><button v-for="t in selected.tags" :key="t" class="lw-tag" @click="cmd = t">#{{ t }}</button></div>
        </section>

        <!-- Structure: topics + entities (claims live in their own verified block below). -->
        <div class="lw-block">
          <ExtractionPanel :text="`${selected.title}. ${selected.summary} ${selected.impact}`" :source="selected.cite" :show-claims="false" />
        </div>
        <div class="lw-block">
          <ClaimsPanel :text="`${selected.summary} ${selected.impact}`" :source="selected.cite" />
        </div>

        <!-- Affected entities — cross-links -->
        <div v-if="crossLinks.length" class="lw-block">
          <div class="lw-block-h">Affected — trace across</div>
          <CrossLinks :links="crossLinks" />
        </div>

        <!-- Depth of treatment (Shepard's citing-references analysis) — how later authority treats this. -->
        <div v-if="citedBy.length" class="lw-block">
          <div class="lw-block-h">Depth of treatment <span class="lw-legend">how {{ citedBy.length }} later authorit{{ citedBy.length === 1 ? 'y' : 'ies' }} treat{{ citedBy.length === 1 ? 's' : '' }} this</span></div>
          <div class="lw-tt-bar" role="img" :aria-label="`${tally.followed} followed, ${tally.superseded} superseded`">
            <span v-if="tally.followed" class="lw-tt-seg followed" :style="{ flex: tally.followed }" />
            <span v-if="tally.superseded" class="lw-tt-seg superseded" :style="{ flex: tally.superseded }" />
          </div>
          <div class="lw-tt-legend"><span><i class="followed" />followed {{ tally.followed }}</span><span><i class="superseded" />negative {{ tally.superseded }}</span></div>
          <div class="lw-tt-list">
            <button v-for="c in citedBy" :key="c.d.id" class="lw-tt-cite" :class="c.treat" @click="goDocket(c.d.id)">
              <span class="lw-tt-flag">{{ c.treat === 'followed' ? '↳' : '▲' }}</span>
              <code>{{ c.d.cite }}</code><span class="lw-tt-title">{{ c.d.title }}</span>
              <span class="lw-tt-tag">{{ c.treat }}</span>
            </button>
          </div>
        </div>

        <!-- Citation network — the authority web as an evidence-backed ego-net (cites + cited-by) -->
        <div v-if="citationLinks.length" class="lw-block">
          <div class="lw-block-h">Citation network <span class="lw-legend">evidence-backed · HellGraph</span></div>
          <EvidenceGraph
            :center="{ id: selected.id, label: selected.cite, type: selected.type }"
            :links="citationLinks"
            :w="300"
            :h="200"
            @select="(n) => goDocket(n.id)"
            @evidence="onCiteEvidence"
          />
          <div class="lw-ego-cap"><span class="d dash"></span>cites <span class="d solid"></span>cited-by · click a node to open · click an edge for the treatment</div>
        </div>

        <!-- Citations (list) -->
        <div v-if="selected.citations.length" class="lw-block">
          <div class="lw-block-h">Cites</div>
          <div class="lw-cites">
            <button v-for="cite in selected.citations" :key="cite.cite" class="lw-cite-link" :class="{ nav: cite.docketId }" :disabled="!cite.docketId" @click="goDocket(cite.docketId)">
              <code>{{ cite.cite }}</code> {{ cite.title }}<span v-if="cite.docketId" class="lw-cite-arrow"> →</span>
            </button>
          </div>
        </div>

        <div class="lw-block">
          <div class="lw-block-h">Redline <span class="lw-legend"><i class="add" />added <i class="del" />removed</span></div>
          <div class="lw-redline">
            <div v-for="(seg, i) in selected.redline" :key="i" class="lw-seg" :class="seg.type">
              <span class="lw-gutter">{{ seg.type === 'add' ? '+' : seg.type === 'del' ? '−' : '' }}</span>
              <span class="lw-seg-text">{{ seg.text }}</span>
            </div>
          </div>
        </div>
      </article>
      <div v-else class="lw-detail empty">Select a docket item</div>
      </template>
    </SplitPane>
  </section>
</template>

<script setup lang="ts">
import SurfaceHeader from '../components/SurfaceHeader.vue';
import LiveToggle from '../components/LiveToggle.vue';
import { fetchFederalRegister } from '../data/adapters/federalRegisterLive';
import { ref, computed, watch, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { dockets, asOf, type Docket, type DocketStatus } from '../data/lawFixture';
import { navScopeForPath } from '../config/cockpitNav';
import { arrowRove } from '../utils/listKeys';
import ProvenanceBadge from '../components/ProvenanceBadge.vue';
import SplitPane from '../components/SplitPane.vue';
import { prov } from '../features/provenance/types';
import CrossLinks from '../components/CrossLinks.vue';
import { crossLinksForDocket } from '../features/crosslink/entityLinks';
import { useCockpit } from '../stores/cockpit';
import ExtractionPanel from '../components/ExtractionPanel.vue';
import EvidenceGraph from '../components/EvidenceGraph.vue';
import { verifyClaims, type Verdict } from '../services/ieApi';
import ClaimsPanel from '../components/ClaimsPanel.vue';

const cockpit = useCockpit();

const statuses = ['all', 'comment', 'pending', 'enacted', 'open'] as const;
const status = ref<(typeof statuses)[number]>('all');
const selectedId = ref<string>(dockets[0]!.id);
const listEl = ref<HTMLElement | null>(null);
const route = useRoute();

// Sub-domain scope: each Law nav leaf narrows the docket set by jurisdiction or
// instrument type, so /law/federal-law, /law/case-law, etc. are real slices of
// the corpus rather than identical boards. A specific ?d= deep-link bypasses the
// scope so palette jumps always resolve, whatever slice the item belongs to.
const scope = computed(() => navScopeForPath(route.path));
const deepLinked = ref(false);
function inScope(d: Docket): boolean {
  if (deepLinked.value) return true;
  switch (route.path) {
    case '/law/federal-law': return d.jurisdiction === 'Federal';
    case '/law/state-local-law': return ['Regional', 'State', 'Local'].includes(d.jurisdiction);
    case '/law/statutory-law': return d.type === 'bill';
    case '/law/case-law': return d.type === 'case';
    case '/law/international-law': return d.jurisdiction === 'International';
    default: return true;
  }
}
onMounted(() => { const d = typeof route.query.d === 'string' ? route.query.d : ''; if (d && dockets.some((x) => x.id === d)) { deepLinked.value = true; status.value = 'all'; selectedId.value = d; } });
// Live search: the box filters the docket list (cite / title / agency / #tag);
// GO selects the first match.
const cmd = ref('');
function runCmd() { if (results.value[0]) selectedId.value = results.value[0].id; }

// Live dockets from the real U.S. Federal Register (opt-in, fails closed to fixture).
const liveState = ref<'idle' | 'loading' | 'live' | 'error'>('idle');
const liveDockets = ref<Docket[] | null>(null);
const isLive = computed(() => liveState.value === 'live' && !!liveDockets.value);
const activeDockets = computed<Docket[]>(() => liveDockets.value ?? dockets);
async function goLive() {
  if (liveState.value === 'loading') return;
  if (liveState.value === 'live') { liveState.value = 'idle'; liveDockets.value = null; return; }
  liveState.value = 'loading';
  const r = await fetchFederalRegister();
  if (r) { liveDockets.value = r; liveState.value = 'live'; }
  else liveState.value = 'error';
}
const results = computed<Docket[]>(() => {
  const needle = cmd.value.trim().toLowerCase();
  return activeDockets.value.filter((d) => (isLive.value || inScope(d))
    && (status.value === 'all' || d.status === (status.value as DocketStatus))
    && (!needle || d.title.toLowerCase().includes(needle) || d.cite.toLowerCase().includes(needle)
      || d.agency.toLowerCase().includes(needle) || d.tags.some((t) => t.includes(needle))));
});
const selected = computed<Docket | undefined>(() => activeDockets.value.find((d) => d.id === selectedId.value));
function setStatus(s: (typeof statuses)[number]) { status.value = s; }

// Moat + integration: provenance verdict, affected-entity cross-links, assistant.
const crossLinks = computed(() => (selected.value ? crossLinksForDocket(selected.value.affects) : []));
// When live, the docket is genuinely RETRIEVED from the Federal Register — it earns
// 'grounded' with a real citation (document number) as the receipt + a real source
// link. When on the illustrative corpus it stays 'fixture'/unassayed (no fake hash).
const docketProv = computed(() => (isLive.value
  ? prov('retrieved', {
      verifier: selected.value?.agency ?? 'U.S. Federal Register',
      sources: [`Federal Register · ${selected.value?.cite ?? ''}`],
      receipt: selected.value?.cite,
      asOf: asOfLabel,
      note: `Retrieved from the U.S. Federal Register${selected.value?.url ? ` — ${selected.value.url}` : ''}.`,
    })
  : prov('fixture', {
      verifier: selected.value?.agency ?? 'issuing body',
      sources: [selected.value?.cite ?? 'docket'],
      asOf: asOfLabel,
      note: 'Illustrative docket for the demo — not retrieved from a live regulatory source; the citation, reference and redline are sample data.',
    })));
function goDocket(id?: string) { if (id) { deepLinked.value = true; selectedId.value = id; } }

// Citation ego-net: outgoing cites (dashed) + derived cited-by (solid) — the authority web.
const citationLinks = computed(() => {
  const s = selected.value;
  if (!s) return [] as Array<{ node: { id: string; label: string; type: string }; rel: string; provenance: 'record' | 'news' | 'personal' | 'derived'; dir: 'in' | 'out'; evidence?: string }>;
  const out = s.citations.map((c) => ({
    node: { id: c.docketId ?? c.cite, label: c.cite, type: 'rule' },
    rel: 'cites', provenance: 'derived' as const, dir: 'out' as const, evidence: c.docketId ? `docket:${c.docketId}` : undefined,
  }));
  const citedBy = dockets
    .filter((d) => d.id !== s.id && d.citations.some((c) => c.docketId === s.id || c.cite === s.cite))
    .map((d) => ({
      node: { id: d.id, label: d.cite, type: d.type }, rel: 'cited by', provenance: 'record' as const, dir: 'in' as const, evidence: `docket:${d.id}`,
    }));
  return [...out, ...citedBy];
});
function onCiteEvidence(lk: { rel?: string; node: { label: string } }) {
  cockpit.askAbout(`For ${selected.value?.cite}, what is the citation treatment of ${lk.node.label} (${lk.rel}) — is it followed, distinguished, questioned, or overruled? Cite the passage.`);
}

// Citator — the "is this still good law?" validity flag (Shepard's/KeyCite equivalent). Wired to the
// LIVE holmes deduction engine (/svc/holmes/verify): the docket's impact claim is checked against
// graph evidence. Falls back to the in-force heuristic when holmes is unreachable or has no evidence
// yet (the graph is still filling in via the News→IE→graph loop) — so it never mis-flags.
const holmesVerdict = ref<Verdict | null>(null);
watch(selected, async (d) => {
  holmesVerdict.value = null;
  const claim = d?.impact || d?.summary;
  if (!claim) return;
  try {
    const r = await verifyClaims([claim]);
    holmesVerdict.value = r.results?.[0] ?? null;
  } catch { holmesVerdict.value = null; } // holmes not reachable yet → heuristic
}, { immediate: true });

// ── Treatment (the citator) — a Shepard's/KeyCite-grade "can I rely on this?" signal.
// One model, used both as the dominant banner on the open docket AND as a per-row
// flag down the list (Tufte small multiples: scan the whole corpus' health at a glance).
// Negative treatment (superseded/overruled) dominates; then a positive holmes signal;
// then structural signals (cited-by-later, in-force). Deterministic + explainable.
type TreatKind = 'good' | 'caution' | 'negative' | 'pending';
interface Treatment { kind: TreatKind; glyph: string; label: string; why: string }

function citingLater(d: Docket): Docket[] {
  return activeDockets.value.filter((x) => x.id !== d.id
    && x.citations.some((c) => c.docketId === d.id || c.cite === d.cite));
}
function treatmentOf(d: Docket, hv?: Verdict | null): Treatment {
  if (d.supersededBy) {
    const by = activeDockets.value.find((x) => x.id === d.supersededBy);
    const overruled = d.type === 'case';
    return { kind: 'negative', glyph: '▲', label: overruled ? 'OVERRULED' : 'SUPERSEDED IN PART',
      why: overruled
        ? `Overruled by a later decision${by ? ` (${by.cite})` : ''} — no longer good law on the point.`
        : `A later authority${by ? ` (${by.cite})` : ''} supersedes part of this — do not rely on the superseded provision.` };
  }
  if (hv?.verdict === 'supported') {
    return { kind: 'good', glyph: '●', label: 'GOOD LAW',
      why: `holmes: supported by ${hv.evidence_count} graph fact(s)${hv.matched_terms?.length ? ' · ' + hv.matched_terms.join(', ') : ''}.` };
  }
  const later = citingLater(d);
  if (later.length) {
    return { kind: 'caution', glyph: '◐', label: 'CAUTION',
      why: `Cited by ${later.length} later authorit${later.length === 1 ? 'y' : 'ies'} (${later.map((x) => x.cite).join(', ')}) — check treatment.` };
  }
  if (hv?.verdict === 'weakly-supported') {
    return { kind: 'caution', glyph: '◐', label: 'CAUTION', why: `holmes: weakly supported (${hv.evidence_count} fact(s)) — check treatment.` };
  }
  if (d.status === 'enacted') return { kind: 'good', glyph: '●', label: 'GOOD LAW', why: 'In force; no distinguishing authority found.' };
  if (d.status === 'comment' || d.status === 'pending') return { kind: 'pending', glyph: '○', label: 'PENDING', why: 'Not yet in force — no binding effect yet.' };
  return { kind: 'good', glyph: '●', label: 'IN EFFECT', why: 'No negative treatment found.' };
}
// The open docket's banner uses the live holmes verdict; row flags use the cheap structural read.
const treatment = computed<Treatment>(() => (selected.value ? treatmentOf(selected.value, holmesVerdict.value) : { kind: 'pending', glyph: '○', label: '—', why: '' }));

// Depth-of-treatment (Shepard's): who cites this, and how. The superseding authority is
// flagged 'superseded'; everything else 'followed' — a compact citing-references tally.
type CiteTreat = 'followed' | 'superseded' | 'overruled';
const citedBy = computed(() => {
  const s = selected.value; if (!s) return [] as { d: Docket; treat: CiteTreat }[];
  return citingLater(s).map((d) => {
    const treat: CiteTreat = s.supersededBy === d.id ? (s.type === 'case' ? 'overruled' : 'superseded') : 'followed';
    return { d, treat };
  });
});
const tally = computed(() => ({
  followed: citedBy.value.filter((c) => c.treat === 'followed').length,
  superseded: citedBy.value.filter((c) => c.treat !== 'followed').length, // superseded | overruled
}));

// Lifecycle rail: map the docket status onto comment → pending → enacted → effective.
const lifecycle = computed(() => {
  const s = selected.value;
  const st = s?.status ?? 'pending';
  const idx = st === 'comment' ? 0 : st === 'enacted' ? 2 : 1; // pending/open → 1
  const effectiveReached = st === 'enacted' && !!s?.effectiveDate && /^\d/.test(s.effectiveDate);
  const cur = effectiveReached ? 3 : idx;
  return [
    { key: 'comment', label: 'Comment' },
    { key: 'pending', label: 'Pending' },
    { key: 'enacted', label: 'Enacted' },
    { key: 'effective', label: 'Effective' },
  ].map((sg, i) => ({ ...sg, state: i < cur ? 'done' : i === cur ? 'now' : 'todo' }));
});
function askNoetica() {
  const d = selected.value; if (!d) return;
  const tail = isLive.value
    ? 'This is a real, retrieved Federal Register filing — you may reason about the specific citation.'
    : 'Note: this is an illustrative sample docket for a demo, not a real retrieved filing — reason about the type of matter, not the specific citation as fact.';
  cockpit.askAbout(`Explain ${d.cite} — "${d.title}" (${d.type}, ${d.status}, ${d.jurisdiction}, issued by ${d.agency}). ${d.impact} Who is most affected, and what is the concrete compliance ask? ${tail}`);
}
watch(selected, (d) => { if (d) cockpit.setContext({ surface: 'Law & Regulation', entityLabel: `${d.cite} · ${d.title}`, detail: `${d.type} · ${d.status}`, route: route.path }); }, { immediate: true });
// Keep a valid selection as the scope/status narrows the visible set.
watch(results, (r) => { if (!r.some((d) => d.id === selectedId.value) && r[0]) selectedId.value = r[0].id; }, { immediate: true });
// Moving between sub-domains resumes scope filtering (deep-link was one-shot).
watch(() => route.path, () => { deepLinked.value = false; });

const NOW = new Date('2026-07-03T14:00:00-04:00').getTime();
function relative(iso: string): string {
  const mins = Math.max(0, Math.round((NOW - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `${mins}m ago`;
  const h = Math.round(mins / 60);
  return h < 24 ? `${h}h ago` : `${Math.round(h / 24)}d ago`;
}
const asOfLabel = new Date(asOf).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
function dateLabel(iso: string): string { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
function countdown(iso: string): string { const days = Math.round((new Date(iso).getTime() - NOW) / 86400000); return days > 0 ? `${days}d left` : days === 0 ? 'today' : 'closed'; }
function deadlineSoon(iso: string): boolean { const days = (new Date(iso).getTime() - NOW) / 86400000; return days >= 0 && days <= 30; }
</script>

<style scoped>
.lw { height: 100%; min-height: 0; display: grid; grid-template-rows: auto 1fr; gap: 0.75rem; padding: 0.85rem 1rem 1rem; background: var(--bg); color: rgba(255, 255, 255, 0.9); }
.lw-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.lw-title { display: flex; align-items: baseline; gap: 0.6rem; } .lw-title h1 { margin: 0; font-size: 1.2rem; letter-spacing: -0.01em; color: var(--text); font-weight: 640; }
.lw-eyebrow { margin: 0 0 0.1rem; font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-3); }
.lw-pill { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--amber); background: var(--amber-soft); border-radius: 5px; padding: 0.1rem 0.35rem; white-space: nowrap; }
.lw-pill.live { color: var(--live); background: var(--live-soft); }
.lw-filters { display: flex; gap: 0.25rem; }
.lw-fbtn { border: 1px solid var(--line-2); background: transparent; color: rgba(255, 255, 255, 0.6); border-radius: 8px; padding: 0.3rem 0.6rem; font-size: 0.74rem; text-transform: capitalize; cursor: pointer; } .lw-fbtn.on { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }

.lw-body { min-height: 0; display: grid; grid-template-columns: minmax(340px, 1fr) minmax(400px, 1.3fr); gap: 0.75rem; }
@media (max-width: 1080px) { .lw-body { grid-template-columns: 1fr; } .lw-detail { display: none; } }

.lw-list { min-height: 0; overflow-y: auto; border: 1px solid var(--line-2); border-radius: 12px; }
.lw-count { margin: 0; padding: 0.5rem 0.85rem; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.08em; color: rgba(255, 255, 255, 0.4); border-bottom: 1px solid var(--line); }
.lw-row { width: 100%; display: grid; gap: 0.25rem; border: none; border-bottom: 1px solid var(--line); background: transparent; color: inherit; padding: 0.65rem 0.85rem; cursor: pointer; text-align: left; } .lw-row:hover { background: rgba(255, 255, 255, 0.03); } .lw-row.on { background: var(--accent-soft); box-shadow: inset 3px 0 0 var(--accent); }
.lw-row-top { display: flex; align-items: center; gap: 0.5rem; }
.lw-cite { font-size: 0.68rem; color: rgba(255, 255, 255, 0.45); font-family: ui-monospace, monospace; }
.lw-row-title { font-size: 0.9rem; font-weight: 600; } .lw-row-meta { font-size: 0.7rem; color: rgba(255, 255, 255, 0.45); }
.lw-empty { padding: 1.5rem; color: rgba(255, 255, 255, 0.45); font-size: 0.85rem; }

.lw-type { font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; border-radius: 4px; padding: 0.05rem 0.35rem; } .lw-type.rule { color: #58a6ff; background: rgba(88, 166, 255, 0.14); } .lw-type.bill { color: #c58af9; background: rgba(197, 138, 249, 0.14); } .lw-type.case { color: #e3b341; background: rgba(227, 179, 65, 0.14); }
.lw-status { font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; border-radius: 999px; padding: 0.05rem 0.4rem; margin-left: auto; } .lw-status.comment { color: #58a6ff; background: rgba(88, 166, 255, 0.14); } .lw-status.pending { color: #e3b341; background: rgba(227, 179, 65, 0.16); } .lw-status.enacted { color: var(--up); background: rgba(63, 185, 80, 0.16); } .lw-status.open { color: #8b949e; background: rgba(139, 148, 158, 0.16); }

.lw-detail { min-height: 0; overflow-y: auto; border: 1px solid var(--line-2); border-radius: 12px; padding: 0 1.1rem 1.1rem; }
.lw-detail.empty { display: grid; place-items: center; color: var(--text-3); font-size: 0.85rem; padding: 1.1rem; }
.lw-ribbon { display: flex; align-items: center; gap: 0.6rem; margin: 0 -1.1rem 0.9rem; padding: 0.4rem 1.1rem; background: var(--accent-soft); border-bottom: 1px solid var(--line-2); font-size: 0.7rem; }
.lw-ribbon-k { text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent); font-weight: 700; font-size: 0.6rem; } .lw-ribbon code { color: rgba(255, 255, 255, 0.6); font-family: ui-monospace, monospace; } .lw-ribbon-as { margin-left: auto; color: rgba(255, 255, 255, 0.4); }
.lw-d-head { display: flex; align-items: center; gap: 0.5rem; margin-top: 1rem; }
.lw-d-head .lw-status { margin-left: 0; }
/* Citator — the "still good law?" validity flag (Shepard's/KeyCite equivalent) */
.lw-citator { margin-left: auto; font-size: 0.62rem; font-weight: 800; letter-spacing: 0.05em; border-radius: 5px; padding: 0.1rem 0.45rem; border: 1px solid; cursor: help; }
.lw-citator.good { color: var(--up); border-color: rgba(75, 191, 115, 0.45); background: rgba(75, 191, 115, 0.1); }
.lw-citator.amber { color: #e3b341; border-color: rgba(227, 179, 65, 0.45); background: rgba(227, 179, 65, 0.1); }
.lw-citator.flat { color: var(--text-3); border-color: var(--line-2); }

/* ── Treatment (citator) system — one visual language for "can I rely on this?" ── */
/* Per-row flag in the docket list (small multiples: scan corpus health at a glance) */
.lw-treat { font-size: 0.7rem; line-height: 1; width: 0.9rem; text-align: center; flex: 0 0 auto; }
.lw-treat.good { color: var(--up); } .lw-treat.caution { color: #e3b341; } .lw-treat.negative { color: var(--down); } .lw-treat.pending { color: rgba(255,255,255,0.3); }
.lw-d-kicker { display: flex; align-items: center; gap: 0.5rem; margin-top: 1rem; }
/* The dominant banner — the first thing you read on the open docket. */
.lw-treat-banner { display: flex; align-items: flex-start; gap: 0.6rem; margin: 0.7rem 0 0.2rem; padding: 0.6rem 0.75rem; border: 1px solid var(--line-2); border-left-width: 4px; border-radius: 10px; background: var(--surface-2, rgba(255,255,255,0.015)); }
.lw-treat-banner.good { border-left-color: var(--up); background: rgba(63,185,80,0.06); }
.lw-treat-banner.caution { border-left-color: #e3b341; background: rgba(227,179,65,0.07); }
.lw-treat-banner.negative { border-left-color: var(--down); background: rgba(248,81,73,0.07); }
.lw-treat-banner.pending { border-left-color: rgba(255,255,255,0.25); }
.lw-tb-glyph { font-size: 1.05rem; line-height: 1.2; flex: 0 0 auto; }
.lw-treat-banner.good .lw-tb-glyph { color: var(--up); } .lw-treat-banner.caution .lw-tb-glyph { color: #e3b341; } .lw-treat-banner.negative .lw-tb-glyph { color: var(--down); } .lw-treat-banner.pending .lw-tb-glyph { color: rgba(255,255,255,0.4); }
.lw-tb-body { flex: 1; min-width: 0; }
.lw-tb-label { display: flex; align-items: center; gap: 0.5rem; font-size: 0.86rem; font-weight: 800; letter-spacing: 0.03em; color: var(--text); }
.lw-treat-banner.good .lw-tb-label { color: #86efac; } .lw-treat-banner.caution .lw-tb-label { color: #e3b341; } .lw-treat-banner.negative .lw-tb-label { color: #fca5a5; }
.lw-tb-src { font-size: 0.54rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-3); border: 1px solid var(--line-2); border-radius: 4px; padding: 0.04rem 0.3rem; }
.lw-tb-why { font-size: 0.78rem; line-height: 1.5; color: rgba(255,255,255,0.72); margin-top: 0.15rem; }
.lw-tb-meta { display: flex; flex-direction: column; align-items: flex-end; gap: 0.15rem; flex: 0 0 auto; font-size: 0.64rem; color: var(--text-3); text-align: right; } .lw-tb-meta b { color: var(--text-2); font-variant-numeric: tabular-nums; }

/* Inline metadata (replaces the fact boxes) */
.lw-meta-line { display: flex; flex-wrap: wrap; gap: 0.25rem 1.4rem; margin: 0.85rem 0 0; padding: 0.55rem 0 0; border-top: 1px solid var(--line); }
.lw-meta-line > div { display: flex; flex-direction: column; gap: 0.05rem; }
.lw-meta-line dt { font-size: 0.55rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3); }
.lw-meta-line dd { margin: 0; font-size: 0.82rem; color: var(--text); font-variant-numeric: tabular-nums; } .lw-meta-line dd.soon { color: #e3b341; }

/* Content sections (Tufte: light rules, no boxes) */
.lw-section { margin-top: 1.05rem; }
.lw-sec-h { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: rgba(255,255,255,0.4); margin-bottom: 0.35rem; }

/* Depth-of-treatment tally (Shepard's citing-references) */
.lw-tt-bar { display: flex; height: 7px; border-radius: 4px; overflow: hidden; background: var(--line); }
.lw-tt-seg.followed { background: var(--up); } .lw-tt-seg.superseded { background: var(--down); }
.lw-tt-legend { display: flex; gap: 1rem; margin-top: 0.35rem; font-size: 0.66rem; color: var(--text-3); }
.lw-tt-legend i { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 0.3rem; } .lw-tt-legend i.followed { background: var(--up); } .lw-tt-legend i.superseded { background: var(--down); }
.lw-tt-list { display: flex; flex-direction: column; gap: 0.3rem; margin-top: 0.6rem; }
.lw-tt-cite { display: flex; align-items: center; gap: 0.5rem; text-align: left; border: 1px solid var(--line-2); border-left-width: 3px; background: var(--surface-2, rgba(255,255,255,0.015)); color: var(--text-2); border-radius: 8px; padding: 0.4rem 0.6rem; font-size: 0.78rem; cursor: pointer; }
.lw-tt-cite.followed { border-left-color: var(--up); } .lw-tt-cite.superseded, .lw-tt-cite.overruled { border-left-color: var(--down); }
.lw-tt-cite:hover { border-color: var(--accent); }
.lw-tt-flag { flex: 0 0 auto; } .lw-tt-cite.superseded .lw-tt-flag { color: var(--down); } .lw-tt-cite.followed .lw-tt-flag { color: var(--text-3); }
.lw-tt-cite code { color: rgba(255,255,255,0.9); font-family: ui-monospace, monospace; font-size: 0.72rem; }
.lw-tt-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lw-tt-tag { font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; border-radius: 999px; padding: 0.05rem 0.4rem; } .lw-tt-cite.followed .lw-tt-tag { color: var(--up); background: rgba(63,185,80,0.14); } .lw-tt-cite.superseded .lw-tt-tag { color: var(--down); background: rgba(248,81,73,0.14); }
/* Lifecycle timeline */
.lw-timeline { display: flex; align-items: center; margin: 0.7rem 0 0.2rem; }
.lw-tl-step { display: flex; flex-direction: column; align-items: center; gap: 0.2rem; font-size: 0.6rem; color: var(--text-3); }
.lw-tl-step.done { color: var(--text-2); } .lw-tl-step.now { color: var(--accent); font-weight: 700; }
.lw-tl-dot { width: 8px; height: 8px; border-radius: 50%; background: rgba(237, 238, 242, 0.18); }
.lw-tl-step.done .lw-tl-dot { background: var(--text-2); }
.lw-tl-step.now .lw-tl-dot { background: var(--accent); box-shadow: 0 0 0 3px rgba(216, 162, 80, 0.18); }
.lw-tl-bar { flex: 1; height: 1.5px; background: rgba(237, 238, 242, 0.12); margin: 0 3px; margin-bottom: 0.85rem; }
.lw-tl-bar.done { background: var(--text-2); }
.lw-d-title { margin: 0.5rem 0 0.3rem; font-size: 1.35rem; line-height: 1.25; }
.lw-d-meta { font-size: 0.76rem; color: rgba(255, 255, 255, 0.5); font-family: ui-monospace, monospace; }
.lw-d-summary { margin: 0.7rem 0 0; font-size: 0.9rem; line-height: 1.6; color: rgba(255, 255, 255, 0.8); }
.lw-ask { border: 1px solid rgba(120, 160, 255, 0.45); background: rgba(120, 160, 255, 0.08); color: #93b4ff; border-radius: 7px; padding: 0.15rem 0.5rem; font-size: 0.7rem; cursor: pointer; } .lw-ask:hover { background: rgba(120, 160, 255, 0.16); color: #fff; }
.lw-facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr)); gap: 0.5rem; margin-top: 0.9rem; }
.lw-fact { display: flex; flex-direction: column; gap: 0.1rem; border: 1px solid var(--line-2); border-radius: 9px; padding: 0.4rem 0.6rem; }
.lw-fact span { font-size: 0.56rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-3); }
.lw-fact b { font-size: 0.82rem; color: var(--text); } .lw-fact b.soon { color: #e3b341; }
.lw-impact { margin: 0; font-size: 0.86rem; line-height: 1.55; color: rgba(255, 255, 255, 0.82); }
.lw-tags { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.6rem; }
.lw-tag { border: 1px solid var(--line-2); background: rgba(255, 255, 255, 0.05); color: var(--text-2); border-radius: 999px; padding: 0.08rem 0.5rem; font-size: 0.68rem; cursor: pointer; } .lw-tag:hover { border-color: #58a6ff; color: #58a6ff; }
.lw-cites { display: flex; flex-direction: column; gap: 0.35rem; }
.lw-cite-link { text-align: left; border: 1px solid var(--line-2); background: var(--surface-2); color: var(--text-2); border-radius: 8px; padding: 0.4rem 0.6rem; font-size: 0.78rem; cursor: default; } .lw-cite-link code { color: rgba(255,255,255,0.9); font-family: ui-monospace, monospace; font-size: 0.72rem; }
.lw-cite-link.nav { cursor: pointer; } .lw-cite-link.nav:hover { border-color: var(--accent); color: var(--accent); }
.lw-cite-arrow { color: var(--accent); }
.lw-block { margin-top: 1rem; border-top: 1px solid var(--line-2); padding-top: 0.85rem; }
.lw-block-h { display: flex; align-items: center; justify-content: space-between; font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: rgba(255, 255, 255, 0.4); margin-bottom: 0.6rem; }
.lw-legend { display: flex; align-items: center; gap: 0.4rem; text-transform: none; letter-spacing: 0; color: rgba(255, 255, 255, 0.4); } .lw-legend i { width: 9px; height: 9px; border-radius: 2px; display: inline-block; margin-right: 0.2rem; } .lw-legend i.add { background: var(--up); } .lw-legend i.del { background: var(--down); }
.lw-ego-cap { display: flex; align-items: center; flex-wrap: wrap; gap: 0.35rem 0.6rem; margin-top: 0.3rem; font-size: 0.62rem; color: var(--text-3); }
.lw-ego-cap .d { display: inline-block; width: 12px; height: 0; }
.lw-ego-cap .d.solid { border-top: 1.5px solid var(--text-2); } .lw-ego-cap .d.dash { border-top: 1.5px dashed var(--accent); }
.lw-redline { border: 1px solid var(--line-2); border-radius: 8px; overflow: hidden; font-family: ui-monospace, 'SF Mono', monospace; font-size: 0.8rem; }
.lw-seg { display: flex; gap: 0.5rem; padding: 0.2rem 0.6rem; line-height: 1.5; white-space: pre-wrap; }
.lw-seg.ctx { color: rgba(255, 255, 255, 0.6); } .lw-seg.add { background: rgba(63, 185, 80, 0.12); color: #86efac; } .lw-seg.del { background: rgba(248, 81, 73, 0.12); color: #fca5a5; }
.lw-gutter { width: 0.8rem; flex: 0 0 auto; text-align: center; color: inherit; opacity: 0.7; } .lw-seg-text { flex: 1; }
</style>
