// Living ontology — the schema-on-the-fly loop. The extraction schema is the base
// ontology (classes, topics, relations); as the corpus is read, it INDUCES the
// ontology: new entity instances per class (lexical variants), the relation
// vocabulary (predicates), and topic frequencies. Ontology guides extraction;
// extraction grows the ontology. Persisted.
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { ENTITY_TYPES, TOPIC_TAXONOMY, type ExtractedEntity } from '../features/extraction/schema';

const KEY = 'sp-ontology-v1';
interface Induced { instances: Record<string, string[]>; predicates: Record<string, number>; topics: Record<string, number> }
function load(): Induced {
  try { const raw = localStorage.getItem(KEY); const p = raw ? JSON.parse(raw) : null; if (p && p.instances) return p; } catch { /* */ }
  return { instances: {}, predicates: {}, topics: {} };
}

export const useOntology = defineStore('ontology', () => {
  const induced = ref<Induced>(load());
  function persist() { try { localStorage.setItem(KEY, JSON.stringify(induced.value)); } catch { /* */ } }

  // NLP → ontology: fold observed entities / predicates / topics into the ontology.
  function observe(entities: ExtractedEntity[], predicates: string[], topics: string[]) {
    let changed = false;
    for (const e of entities) {
      const arr = (induced.value.instances[e.class] ??= []);
      if (!arr.some((x) => x.toLowerCase() === e.text.toLowerCase()) && arr.length < 60) { arr.push(e.text); changed = true; }
    }
    for (const p of predicates) { induced.value.predicates[p] = (induced.value.predicates[p] ?? 0) + 1; changed = true; }
    for (const t of topics) { induced.value.topics[t] = (induced.value.topics[t] ?? 0) + 1; changed = true; }
    if (changed) persist();
  }
  function reset() { induced.value = { instances: {}, predicates: {}, topics: {} }; persist(); }

  // Ontology → extraction: the classes/topics that guide the extractor.
  const classes = computed(() => ENTITY_TYPES.map((t) => ({ ...t, instances: induced.value.instances[t.class] ?? [] })));
  const relations = computed(() => Object.entries(induced.value.predicates).sort((a, b) => b[1] - a[1]).map(([predicate, count]) => ({ predicate, count })));
  const topics = computed(() => Object.entries(induced.value.topics).sort((a, b) => b[1] - a[1]).map(([topic, count]) => ({ topic, count, base: Object.keys(TOPIC_TAXONOMY).includes(topic) })));
  const stats = computed(() => ({
    classes: ENTITY_TYPES.length,
    instances: Object.values(induced.value.instances).reduce((s, a) => s + a.length, 0),
    relations: Object.keys(induced.value.predicates).length,
    topics: Object.keys(induced.value.topics).length,
  }));

  return { induced, observe, reset, classes, relations, topics, stats };
});
