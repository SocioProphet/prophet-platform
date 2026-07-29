/**
 * W11.5 — the KnowledgeNugget feed.
 *
 * The contract under test is the schema's own normative rule: model-generated content stays
 * VISIBLY distinguishable, and no path may launder it into something source-warranted. Plus
 * the estate's fixture-honesty rule: a failed live read never quietly becomes fixture proof.
 *
 *   1. Fixture integrity — direct-quote spans really do slice out of the hashed source.
 *   2. parseNugget is fail-closed, and unreadable is UNKNOWN, not a failure verdict.
 *   3. The span is passed to <Warrant> only when it genuinely warrants the text.
 *   4. A nugget's seal is `unknown` — never sealed, never unsealed.
 *   5. The card makes direct-quote and model-generated read differently.
 *   6. The service: live / live-but-empty / unreachable are three different outcomes.
 */
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';
import NuggetCard from '../components/nuggets/NuggetCard.vue';
import StudioNuggets from '../pages/studio/StudioNuggets.vue';
import {
  FIXTURE_CONTENT_HASH,
  FIXTURE_MALFORMED,
  FIXTURE_NUGGETS,
  FIXTURE_SOURCE_TEXT,
} from '../data/nuggetFixture';
import { nuggetWarrantInput, parseNugget, type KnowledgeNugget } from '../features/nuggets/types';
import { fetchNuggets } from '../services/nuggetApi';
import { isModelGenerated, isSourceWarranted, warrantView } from '../features/warrant/types';

const byType = (t: string) => FIXTURE_NUGGETS.find((n) => n.warrant.type === t)!;
const QUOTE = byType('direct-quote');
const COMPUTED = byType('computed');
const MODEL = byType('model-generated');
const INFERRED = byType('inferred');

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('nugget fixture — faithful to the producer', () => {
  it('every direct-quote span slices back out of the hashed source, exactly', () => {
    const quotes = FIXTURE_NUGGETS.filter((n) => n.warrant.type === 'direct-quote');
    expect(quotes.length).toBeGreaterThan(0);
    for (const n of quotes) {
      const { start, end } = n.sourceRef.span;
      expect(FIXTURE_SOURCE_TEXT.slice(start, end)).toBe(n.text);
      // The family validator's invariant for direct-quote.
      expect(end - start).toBe(n.text.length);
    }
  });

  it('every span lies inside the source and is well-ordered', () => {
    for (const n of FIXTURE_NUGGETS) {
      const { start, end } = n.sourceRef.span;
      expect(end).toBeGreaterThanOrEqual(start);
      expect(end).toBeLessThanOrEqual(FIXTURE_SOURCE_TEXT.length);
      expect(n.sourceRef.contentHash).toBe(FIXTURE_CONTENT_HASH);
    }
  });

  it('derived warrants cite evidence; model-generated need not', () => {
    for (const n of FIXTURE_NUGGETS) {
      if (n.warrant.type === 'computed' || n.warrant.type === 'inferred') {
        expect(n.warrant.evidence.length).toBeGreaterThan(0);
      }
    }
    expect(MODEL.warrant.evidence).toEqual([]);
  });

  it('every cited evidence ref resolves to a nugget in the feed', () => {
    const ids = new Set(FIXTURE_NUGGETS.map((n) => n.id));
    const derived = FIXTURE_NUGGETS.filter(
      (n) => n.warrant.type === 'computed' || n.warrant.type === 'inferred',
    );
    expect(derived.length).toBeGreaterThan(0);
    for (const n of derived) {
      for (const ref of n.warrant.evidence) expect(ids.has(ref)).toBe(true);
    }
  });

  it('a computed nugget is warranted by a direct quote, not by another derivation', () => {
    const quoteIds = new Set(
      FIXTURE_NUGGETS.filter((n) => n.warrant.type === 'direct-quote').map((n) => n.id),
    );
    for (const n of FIXTURE_NUGGETS.filter((x) => x.warrant.type === 'computed')) {
      expect(n.warrant.evidence.every((e) => quoteIds.has(e))).toBe(true);
    }
  });
});

describe('parseNugget — fail-closed', () => {
  it('accepts every fixture nugget', () => {
    for (const n of FIXTURE_NUGGETS) expect(parseNugget(n).ok).toBe(true);
  });

  it('rejects a computed warrant that cites no evidence, and says why', () => {
    const r = parseNugget(FIXTURE_MALFORMED, 'node-1');
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.reason).toContain('cites no evidence');
      expect(r.nodeId).toBe('node-1');
    }
  });

  it('refuses an unrecognized warrant type instead of downgrading it to a known one', () => {
    const r = parseNugget({ ...QUOTE, warrant: { ...QUOTE.warrant, type: 'vibes' } });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain('unrecognized warrant.type');
  });

  it('names the missing field rather than defaulting it', () => {
    const { text: _drop, ...noText } = QUOTE;
    const r = parseNugget(noText);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('missing text');
  });
});

describe('nuggetWarrantInput — no laundering', () => {
  it('gives <Warrant> a source span ONLY for a direct quote', () => {
    expect(nuggetWarrantInput(QUOTE).span).toBeDefined();
    // For these the span is a conditioning/source window; it does not warrant the text.
    expect(nuggetWarrantInput(MODEL).span).toBeUndefined();
    expect(nuggetWarrantInput(COMPUTED).span).toBeUndefined();
    expect(nuggetWarrantInput(INFERRED).span).toBeUndefined();
  });

  it('carries the warrant type through unchanged', () => {
    for (const n of FIXTURE_NUGGETS) {
      expect(warrantView(nuggetWarrantInput(n)).kind).toBe(n.warrant.type);
    }
  });

  it('resolves every nugget to seal UNKNOWN — not sealed, not unsealed', () => {
    for (const n of FIXTURE_NUGGETS) {
      const v = warrantView(nuggetWarrantInput(n));
      expect(v.seal).toBe('unknown');
      expect(v.sealLabel).toBe('unknown');
    }
  });

  it('gives NO nugget a confident ramp mode, however strong its warrant', () => {
    // #1052's rule: only a SEALED claim keeps a confident ramp. A nugget carries no receipt,
    // so its seal is unknown — and a direct quote gets exactly the same desaturated ramp as a
    // model guess. Warrant kind and seal state are different axes; the ramp answers the seal
    // one, and the card separates the warrant one by hue and by the label.
    for (const n of FIXTURE_NUGGETS) {
      expect(warrantView(nuggetWarrantInput(n)).epistemic).toBe('unknown');
    }
    // …while the warrant KIND still comes through untouched.
    expect(warrantView(nuggetWarrantInput(QUOTE)).kindLabel).toBe('direct quote');
    expect(warrantView(nuggetWarrantInput(MODEL)).kindLabel).toBe('model-generated');
  });

  it('classifies source-warranted exactly as contract.py SOURCE_WARRANTED does', () => {
    // contract.py :61 — SOURCE_WARRANTED = ("direct-quote", "computed", "inferred")
    expect(isSourceWarranted('direct-quote')).toBe(true);
    expect(isSourceWarranted('computed')).toBe(true);
    expect(isSourceWarranted('inferred')).toBe(true);
    expect(isSourceWarranted('model-generated')).toBe(false);
    // …and the plan-side invented kind is never source-warranted either.
    expect(isSourceWarranted('ungrounded')).toBe(false);
    expect(isModelGenerated('model-generated')).toBe(true);
    expect(isModelGenerated('ungrounded')).toBe(true);
    expect(isModelGenerated('direct-quote')).toBe(false);
  });
});

describe('<NuggetCard> — the difference is visible at a glance', () => {
  const card = (n: KnowledgeNugget, level: 'novice' | 'journeyman' | 'expert' = 'expert') =>
    mount(NuggetCard, { props: { nugget: n, level } });

  it('brands a model-generated nugget three ways at once', () => {
    const w = card(MODEL);
    expect(w.find('.ng').classes()).toContain('ng-model'); // dashed container
    expect(w.find('.ng-banner').exists()).toBe(true); // standing banner
    expect(w.find('.ng-banner').text()).toContain('Not warranted by the source');
    expect(w.find('.ng-kind').text()).toBe('model-generated'); // the label
  });

  it('does not brand a direct quote as model-generated, and styles it as a quotation', () => {
    const w = card(QUOTE);
    expect(w.find('.ng').classes()).not.toContain('ng-model');
    expect(w.find('.ng-banner').exists()).toBe(false);
    expect(w.find('.ng-text').classes()).toContain('quote');
  });

  it('calls the span a conditioning window for model-generated, and a span otherwise', () => {
    expect(card(MODEL).text()).toContain('conditioning window');
    expect(card(QUOTE).text()).not.toContain('conditioning window');
  });

  it('never paints the stripe at full ramp strength, since no nugget is sealed', () => {
    for (const n of FIXTURE_NUGGETS) {
      const style = card(n).find('.ng').attributes('style') ?? '';
      // Hue is present (so a quote still reads differently from a guess)…
      expect(style).toContain('--epi-');
      // …but always mixed down, never the raw token that a SEALED surface would use.
      expect(style).toContain('color-mix');
    }
  });

  it('states the seal as unknown, and explains why there is no receipt', () => {
    const w = card(QUOTE);
    expect(w.find('.ng-seal').text()).toContain('unknown');
    expect(w.find('.ng-seal').text()).toContain('seals the emitted BATCH');
  });

  it('shows a direct quote has no cited evidence WITHOUT implying a defect', () => {
    const w = card(QUOTE);
    expect(w.text()).toContain('grounded by its source span itself');
  });
});

describe('nugget feed service — live, empty and unreachable are three facts', () => {
  const node = (n: KnowledgeNugget) => ({
    id: n.id,
    labels: ['KnowledgeNugget', `warrant:${n.warrant.type}`],
    properties: { nuggetId: n.id, warrantType: n.warrant.type, nugget: JSON.stringify(n) },
  });

  it('parses nuggets out of the graph node property when the read succeeds', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ count: 2, nodes: [node(QUOTE), node(MODEL)] }),
      }),
    );
    const r = await fetchNuggets();
    expect(r.mode).toBe('live');
    expect(r.error).toBeNull();
    expect(r.items.filter((i) => i.ok).length).toBe(2);
  });

  it('reports a reachable-but-empty graph as LIVE and empty — never as fixtures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ count: 0, nodes: [] }) }));
    const r = await fetchNuggets();
    expect(r.mode).toBe('live');
    expect(r.emptyLive).toBe(true);
    expect(r.items).toEqual([]);
  });

  it('falls back to FIXTURE — labelled, with the reason — when the graph is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ECONNREFUSED')));
    const r = await fetchNuggets();
    expect(r.mode).toBe('fixture');
    expect(r.error).toContain('ECONNREFUSED');
    expect(r.items.filter((i) => i.ok).length).toBe(FIXTURE_NUGGETS.length);
  });

  it('treats a non-ok HTTP status as unavailable, not as an empty graph', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({}) }));
    const r = await fetchNuggets();
    expect(r.mode).toBe('fixture');
    expect(r.error).toContain('503');
    expect(r.emptyLive).toBe(false);
  });

  it('keeps a node whose canonical JSON will not parse, as unreadable with a reason', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ count: 1, nodes: [{ id: 'n1', properties: { nugget: '{not json' } }] }),
      }),
    );
    const r = await fetchNuggets();
    expect(r.mode).toBe('live');
    const bad = r.items.find((i) => !i.ok)!;
    expect(bad.ok).toBe(false);
    if (!bad.ok) expect(bad.reason).toContain('did not parse');
  });
});

describe('Studio nugget feed surface', () => {
  it('declares the fixture fallback above everything it renders', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    const w = mount(StudioNuggets);
    await flushPromises();
    const banner = w.find('.nf-mode');
    expect(banner.classes()).toContain('m-fixture');
    expect(banner.text()).toContain('FIXTURE');
    expect(banner.text()).toContain('nothing below came off a graph');
  });

  it('says plainly that delivery is pull, not push', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    const w = mount(StudioNuggets);
    await flushPromises();
    expect(w.find('.nf-pull').text()).toContain('Pull, not push');
  });

  it('does not pass its filters off as access control', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    const w = mount(StudioNuggets);
    await flushPromises();
    const grant = w.find('.nf-grant').text();
    expect(grant).toContain('not grant scoping and not access control');
    expect(grant).toContain('follow-on');
  });

  it('subscribes to every warrant class by default, and discloses what a filter hides', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    const w = mount(StudioNuggets);
    await flushPromises();
    expect(w.findAll('.ng').length).toBe(FIXTURE_NUGGETS.length);

    const modelPill = w.findAll('.nf-sub').find((b) => b.text().startsWith('model-generated'))!;
    await modelPill.trigger('click');
    expect(w.findAll('.ng').length).toBe(FIXTURE_NUGGETS.length - 1);
    expect(w.find('.nf-hidden').text()).toContain('1 readable nugget');
  });

  it('never folds model-generated into a single headline total', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    const w = mount(StudioNuggets);
    await flushPromises();
    const split = w.find('.nf-split');
    expect(split.text()).toContain('source-warranted');
    expect(split.text()).toContain('model-generated');
    const src = FIXTURE_NUGGETS.filter((n) => isSourceWarranted(n.warrant.type)).length;
    expect(w.find('.nf-split-src').text()).toContain(String(src));
    expect(w.find('.nf-split-mod').text()).toContain(String(FIXTURE_NUGGETS.length - src));
  });

  it('lists unreadable payloads rather than dropping them, and calls them unknown', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    const w = mount(StudioNuggets);
    await flushPromises();
    const bad = w.find('.nf-bad');
    expect(bad.exists()).toBe(true);
    expect(bad.text()).toContain('Unreadable is');
    expect(bad.text()).toContain('cites no evidence');
  });

  it('shows a real empty state on a reachable graph, with no fixtures substituted', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ count: 0, nodes: [] }) }));
    const w = mount(StudioNuggets);
    await flushPromises();
    expect(w.find('.nf-empty').exists()).toBe(true);
    expect(w.find('.nf-empty').text()).toContain('not a reason to show you fixtures');
    expect(w.findAll('.ng').length).toBe(0);
  });
});
