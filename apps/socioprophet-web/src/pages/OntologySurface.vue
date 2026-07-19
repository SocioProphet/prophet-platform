<template>
  <section class="on" aria-label="Living ontology">
    <SurfaceHeader title="Living Ontology" eyebrow="Knowledge · schema-on-the-fly">
      <template #badge><span class="on-stat">{{ stats.instances }} instances · {{ stats.relations }} relations</span></template>
      <template #actions>
        <button class="on-ask" type="button" @click="askNoetica">◇ Ask Noetica</button>
        <button class="on-reset" type="button" @click="ontology.reset()" title="Clear induced ontology">Reset</button>
      </template>
    </SurfaceHeader>

    <!-- The bidirectional loop -->
    <div class="on-loop">
      <div class="on-loop-node">Ontology</div>
      <div class="on-loop-arrow">guides →<br /><span>← induces</span></div>
      <div class="on-loop-node">NLP extraction</div>
      <p class="on-loop-note">
        <InfoLabel label="Schema-on-the-fly" info="The ontology guides extraction (which entity classes / relations to look for); the corpus you read induces it back (new instances, relation vocabulary, topics). A living model, not a static schema." />
        — read News &amp; Law and watch the counts grow.
      </p>
    </div>

    <SplitPane storage-key="ontology" label="entities" :initial="420">
      <template #list>
      <!-- Entity classes + induced instances -->
      <div class="on-panel">
        <div class="on-panel-h">Entity classes <span class="on-hint">{{ stats.classes }} · lexical variants induced from the corpus</span></div>
        <div class="on-classes">
          <div v-for="c in classes" :key="c.class" class="on-class">
            <div class="on-class-h"><span class="on-class-dot" :style="{ background: c.color }" />{{ c.label }}<span class="on-class-n">{{ c.instances.length }}</span></div>
            <div v-if="c.instances.length" class="on-instances">
              <span v-for="ins in c.instances.slice(0, 8)" :key="ins" class="on-ins" :style="{ borderColor: c.color + '66', color: c.color }">{{ ins }}</span>
              <span v-if="c.instances.length > 8" class="on-more">+{{ c.instances.length - 8 }}</span>
            </div>
            <p v-else class="on-empty">no instances yet</p>
          </div>
        </div>
      </div>
      </template>

      <template #detail>

      <!-- Induced relations + topics -->
      <div class="on-panel">
        <div class="on-panel-h">Relations <span class="on-hint">predicate vocabulary induced from claims</span></div>
        <div v-if="relations.length" class="on-rels">
          <div v-for="r in relations" :key="r.predicate" class="on-rel">
            <span class="on-rel-p">{{ r.predicate }}</span>
            <span class="on-rel-bar"><span class="on-rel-fill" :style="{ width: relPct(r.count) + '%' }" /></span>
            <span class="on-rel-n">{{ r.count }}</span>
          </div>
        </div>
        <p v-else class="on-empty">No relations induced yet — open a Law docket or news story.</p>

        <div class="on-panel-h" style="margin-top: 1rem">Topics</div>
        <div class="on-topics">
          <span v-for="t in topics" :key="t.topic" class="on-topic" :class="{ base: t.base }">{{ t.topic }} <b>{{ t.count }}</b></span>
          <p v-if="!topics.length" class="on-empty">No topics observed yet.</p>
        </div>
      </div>
      </template>
    </SplitPane>
  </section>
</template>

<script setup lang="ts">
import SplitPane from '../components/SplitPane.vue';
import { computed, onMounted } from 'vue';
import SurfaceHeader from '../components/SurfaceHeader.vue';
import InfoLabel from '../components/InfoLabel.vue';
import { useOntology } from '../stores/ontology';
import { useCockpit } from '../stores/cockpit';
import { extract } from '../features/extraction/schema';
import { reify } from '../features/claims/reify';
import { newsItems } from '../data/newsFeedFixture';
import { dockets } from '../data/lawFixture';

const ontology = useOntology();
const cockpit = useCockpit();
const classes = computed(() => ontology.classes);
const relations = computed(() => ontology.relations);
const topics = computed(() => ontology.topics);
const stats = computed(() => ontology.stats);
const maxRel = computed(() => Math.max(1, ...relations.value.map((r) => r.count)));
const relPct = (n: number) => Math.max(6, (n / maxRel.value) * 100);
function askNoetica() {
  cockpit.askAbout(`Read the living ontology: ${stats.value.instances} entity instances across ${stats.value.classes} classes, ${stats.value.relations} induced relations. What relations are emerging, and does the schema need new classes or constraints?`);
}
// Seed the ontology from the corpus on first visit so the loop is visibly alive
// (the same observe() that reading News + Law performs). Reading more grows it further.
function seedFromCorpus() {
  const feed = (text: string, source: string) => {
    const ex = extract(text);
    const claims = reify(text, source, ex);
    ontology.observe(ex.entities, claims.map((c) => c.predicate), ex.topics);
  };
  for (const it of newsItems) feed(`${it.title}. ${it.summary}`, 'news');
  for (const d of dockets) feed(`${d.title}. ${d.summary} ${d.impact}`, d.cite);
}
onMounted(() => {
  if (stats.value.instances === 0 && stats.value.relations === 0 && stats.value.topics === 0) seedFromCorpus();
  cockpit.setContext({ surface: 'Living Ontology', entityLabel: `${stats.value.instances} instances`, detail: `${stats.value.relations} relations`, route: '/ontology' });
});
</script>

<style scoped>
.on { height: 100%; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 1rem; padding: 1rem 1.25rem 1.5rem; background: var(--bg); color: var(--text); }
.on :deep(.sp2) { flex: 1 1 auto; min-height: 24rem; }
.on-stat { font-size: 0.66rem; color: var(--text-3); }
.on-ask { border: 1px solid rgba(120, 160, 255, 0.45); background: rgba(120, 160, 255, 0.08); color: #93b4ff; border-radius: 8px; padding: 0.35rem 0.7rem; font-size: 0.76rem; cursor: pointer; } .on-ask:hover { background: rgba(120, 160, 255, 0.16); color: #fff; }
.on-reset { border: 1px solid var(--line-2); background: transparent; color: var(--text-3); border-radius: 8px; padding: 0.35rem 0.7rem; font-size: 0.76rem; cursor: pointer; } .on-reset:hover { color: var(--text); }
.on-loop { display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap; border: 1px solid var(--line-2); border-radius: 12px; padding: 0.7rem 0.9rem; background: var(--surface); }
.on-loop-node { font-size: 0.82rem; font-weight: 700; color: var(--text); border: 1px solid var(--line-2); border-radius: 8px; padding: 0.3rem 0.7rem; background: var(--surface-2); }
.on-loop-arrow { font-size: 0.64rem; color: #93b4ff; text-align: center; line-height: 1.5; } .on-loop-arrow span { color: #4bbf73; }
.on-loop-note { margin: 0; margin-left: auto; font-size: 0.78rem; color: var(--text-2); max-width: 36ch; }
.on-grid { display: grid; grid-template-columns: 1.2fr 1fr; gap: 0.9rem; }
@media (max-width: 1000px) { .on-grid { grid-template-columns: 1fr; } }
.on-panel { border: 1px solid var(--line-2); border-radius: 12px; padding: 0.9rem; background: var(--surface); }
.on-panel-h { font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3); margin-bottom: 0.7rem; } .on-hint { text-transform: none; letter-spacing: 0; color: var(--text-3); }
.on-classes { display: flex; flex-direction: column; gap: 0.6rem; }
.on-class-h { display: flex; align-items: center; gap: 0.4rem; font-size: 0.82rem; font-weight: 600; }
.on-class-dot { width: 8px; height: 8px; border-radius: 50%; } .on-class-n { margin-left: auto; font-size: 0.7rem; color: var(--text-3); }
.on-instances { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-top: 0.3rem; }
.on-ins { font-size: 0.68rem; border: 1px solid; border-radius: 6px; padding: 0.05rem 0.4rem; background: rgba(255, 255, 255, 0.03); }
.on-more { font-size: 0.66rem; color: var(--text-3); }
.on-empty { margin: 0.2rem 0 0; font-size: 0.72rem; color: var(--text-3); }
.on-rels { display: flex; flex-direction: column; gap: 0.35rem; }
.on-rel { display: grid; grid-template-columns: 7rem 1fr 2rem; align-items: center; gap: 0.5rem; font-size: 0.76rem; }
.on-rel-p { color: #93b4ff; font-style: italic; }
.on-rel-bar { height: 8px; border-radius: 999px; background: rgba(255, 255, 255, 0.06); overflow: hidden; }
.on-rel-fill { display: block; height: 100%; background: linear-gradient(90deg, #1f6feb, #58a6ff); }
.on-rel-n { text-align: right; color: var(--text-3); font-variant-numeric: tabular-nums; }
.on-topics { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.on-topic { font-size: 0.72rem; color: var(--text-2); border: 1px solid var(--line-2); border-radius: 999px; padding: 0.1rem 0.5rem; } .on-topic.base { color: #a3e635; border-color: rgba(163, 230, 53, 0.3); } .on-topic b { color: var(--text); }
</style>
