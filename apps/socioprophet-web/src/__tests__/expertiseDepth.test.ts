/**
 * W11.6 — expertise-adaptive depth.
 *
 * THE RULE: depth changes what is SHOWN, never what is CLAIMED.
 *
 * The centrepiece is `no gloss ever overstates its warrant` below. Every plain-language
 * reading declares the epistemic strength it conveys, and this suite asserts that equals the
 * strength the warrant actually has — for every warrant kind at every depth. A future edit
 * that softened the novice wording for `model-generated` would fail here rather than ship.
 *
 * The rest pins the floor: the warrant badge, the model-generated banner and the seal state
 * render at EVERY depth, and the stored preference actually persists.
 */
import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import NuggetCard from '../components/nuggets/NuggetCard.vue';
import DepthControl from '../components/depth/DepthControl.vue';
import {
  EXPERTISE_LEVELS,
  WARRANT_STRENGTH,
  clampText,
  depthPolicy,
  isExpertise,
  warrantGloss,
  type Expertise,
} from '../features/depth/expertise';
import { FIXTURE_NUGGETS } from '../data/nuggetFixture';
import { useSettings } from '../stores/settings';
import type { WarrantKind } from '../features/warrant/types';

const KINDS = Object.keys(WARRANT_STRENGTH) as WarrantKind[];
const MODEL = FIXTURE_NUGGETS.find((n) => n.warrant.type === 'model-generated')!;
const QUOTE = FIXTURE_NUGGETS.find((n) => n.warrant.type === 'direct-quote')!;

describe('depth — no gloss ever overstates its warrant', () => {
  it('every (kind × level) gloss conveys exactly the strength the warrant has', () => {
    for (const kind of KINDS) {
      for (const level of EXPERTISE_LEVELS) {
        const g = warrantGloss(kind, level);
        expect(g.text.length).toBeGreaterThan(0);
        // The whole point: the wording may change with depth, the strength may not.
        expect(g.conveys).toBe(WARRANT_STRENGTH[kind]);
      }
    }
  });

  it('a model-generated gloss is never as strong as a direct-quote gloss, at any depth', () => {
    for (const level of EXPERTISE_LEVELS) {
      expect(warrantGloss('model-generated', level).conveys).toBeLessThan(
        warrantGloss('direct-quote', level).conveys,
      );
    }
  });

  it('warns at least as hard for a novice as for an expert', () => {
    // The novice wording for invented content must not be the gentle one.
    expect(warrantGloss('model-generated', 'novice').text).toContain('NOT in the source');
    expect(warrantGloss('ungrounded', 'novice').text).toContain('Invented');
  });

  it('gives an unrecognized warrant the weakest reading rather than a confident one', () => {
    const g = warrantGloss('not-a-real-kind' as WarrantKind, 'expert');
    expect(g.conveys).toBe(0);
    expect(g.text).toContain('unproven');
  });
});

describe('depth — policy gates supporting detail only', () => {
  it('is ordered shallow → deep', () => {
    expect(EXPERTISE_LEVELS.map((l) => depthPolicy(l).rank)).toEqual([0, 1, 2]);
  });

  it('reveals monotonically more as depth increases', () => {
    const flags = [
      'showRawRefs',
      'showSpanOffsets',
      'showEvidenceList',
      'showProvenanceChain',
      'showPolicyLabels',
      'showCanonicalPayload',
      'showLosingCandidates',
      'showConfidence',
    ] as const;
    for (const f of flags) {
      const seq = EXPERTISE_LEVELS.map((l) => Number(depthPolicy(l)[f]));
      // never turns something back OFF as you go deeper
      for (let i = 1; i < seq.length; i++) expect(seq[i]!).toBeGreaterThanOrEqual(seq[i - 1]!);
    }
  });

  it('exposes no flag capable of hiding a warrant, a seal, or the model-generated marker', () => {
    const keys = Object.keys(depthPolicy('novice'));
    for (const forbidden of ['showWarrant', 'showSeal', 'showModelGenerated', 'showWarrantType']) {
      expect(keys).not.toContain(forbidden);
    }
  });

  it('falls back to the shallow policy for an unknown level', () => {
    expect(depthPolicy('wizard' as Expertise).level).toBe('novice');
    expect(isExpertise('wizard')).toBe(false);
    expect(isExpertise('expert')).toBe(true);
  });

  it('clamps text on a word boundary and marks it truncated', () => {
    const long = 'word '.repeat(200).trim();
    const r = clampText(long, depthPolicy('novice'));
    expect(r.truncated).toBe(true);
    expect(r.text.endsWith('…')).toBe(true);
    expect(clampText('short', depthPolicy('novice')).truncated).toBe(false);
    // Expert has no budget at all.
    expect(clampText(long, depthPolicy('expert')).truncated).toBe(false);
  });
});

describe('depth — the honesty floor holds at every level', () => {
  const card = (n = MODEL, level: Expertise = 'novice') =>
    mount(NuggetCard, { props: { nugget: n, level } });

  it('shows the warrant badge and its type at every depth', () => {
    for (const level of EXPERTISE_LEVELS) {
      for (const n of FIXTURE_NUGGETS) {
        const w = card(n, level);
        expect(w.find('.wr').exists()).toBe(true);
        expect(w.find('.ng-kind').text()).toBe(n.warrant.type);
      }
    }
  });

  it('shows the model-generated banner at every depth — novice included', () => {
    for (const level of EXPERTISE_LEVELS) {
      const w = card(MODEL, level);
      expect(w.find('.ng-banner').exists()).toBe(true);
      expect(w.find('.ng').classes()).toContain('ng-model');
    }
  });

  it('shows the unknown seal state at every depth', () => {
    for (const level of EXPERTISE_LEVELS) {
      expect(card(QUOTE, level).find('.ng-seal').text()).toContain('unknown');
    }
  });

  it('never labels a model-generated nugget with a source-warranted word', () => {
    for (const level of EXPERTISE_LEVELS) {
      const t = card(MODEL, level).text();
      expect(t).not.toContain('direct quote');
      expect(t).toContain('model-generated');
    }
  });
});

describe('depth — it genuinely changes what is shown', () => {
  const card = (level: Expertise) =>
    mount(NuggetCard, { props: { nugget: FIXTURE_NUGGETS.find((n) => n.warrant.type === 'computed')!, level } });

  it('hides evidence, payload, provenance and URNs from a novice', () => {
    const w = card('novice');
    expect(w.text()).not.toContain('Evidence');
    expect(w.text()).not.toContain('Canonical');
    expect(w.text()).not.toContain('Provenance');
    expect(w.text()).not.toContain('Content hash');
  });

  it('adds evidence at journeyman and the full record at expert', () => {
    expect(card('journeyman').text()).toContain('Evidence');
    expect(card('journeyman').text()).not.toContain('Canonical');

    const x = card('expert').text();
    expect(x).toContain('Evidence');
    expect(x).toContain('Canonical');
    expect(x).toContain('Provenance');
    expect(x).toContain('nugget-extractor/quantity@v1');
  });

  it('discloses that novice text was shortened rather than silently cutting it', () => {
    const long = { ...QUOTE, text: 'x '.repeat(400).trim() };
    const w = mount(NuggetCard, { props: { nugget: long, level: 'novice' as Expertise } });
    expect(w.find('.ng-trunc').text()).toContain('full text is unchanged');
  });
});

describe('depth — the preference is stored, not per-page', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    try {
      localStorage.clear();
    } catch { /* storage disabled */ }
  });

  it('defaults to novice — the shallow, safe default', () => {
    expect(useSettings().expertise).toBe('novice');
  });

  it('persists a change to localStorage under the shared settings key', async () => {
    const s = useSettings();
    s.setExpertise('expert');
    await new Promise((r) => setTimeout(r, 0));
    const raw = JSON.parse(localStorage.getItem('sp.settings.v1') ?? '{}');
    expect(raw.expertise).toBe('expert');
  });

  it('ignores a corrupt stored value instead of trusting it', () => {
    localStorage.setItem('sp.settings.v1', JSON.stringify({ expertise: 'god-mode' }));
    setActivePinia(createPinia());
    expect(useSettings().expertise).toBe('novice');
  });

  it('the control writes the stored preference', async () => {
    const w = mount(DepthControl);
    const expert = w.findAll('.dc-opt').find((b) => b.text() === 'Expert')!;
    await expert.trigger('click');
    expect(useSettings().expertise).toBe('expert');
    expect(w.find('.dc-opt.on').text()).toBe('Expert');
  });

  it('states the guarantee next to the control', () => {
    expect(mount(DepthControl).find('.dc-vow').text()).toContain('never what is claimed');
  });
});
