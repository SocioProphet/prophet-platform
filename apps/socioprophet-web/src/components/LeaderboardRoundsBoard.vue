<script setup lang="ts">
import { onMounted, ref } from 'vue'

type HeadlineMetric = {
  metric_id: string
  value: number
}

type RoundEntry = {
  entry_id: string
  candidate_id: string
  rank?: number
  tier?: string
  headline: HeadlineMetric
  recipe_proof_ref?: { recipe_proof_id: string }
  doi_ref?: { concept_doi?: string; version_doi?: string }
}

type RankingRule = {
  metric_id: string
  direction: 'higher_is_better' | 'lower_is_better'
  mode: 'ranked' | 'tiered'
}

type Round = {
  round_id: string
  version: string
  division: 'CLOSED' | 'OPEN'
  comparable?: boolean
  published_at?: string
  ranking_rule: RankingRule
  entries: RoundEntry[]
}

type RoundsPayload = {
  rounds: Round[]
  closed_count: number
  open_count: number
  non_comparable_warning: string
  source: string
  non_claims: string[]
}

const payload = ref<RoundsPayload | null>(null)
const error = ref<string | null>(null)
const mode = ref<'loading' | 'live' | 'error'>('loading')

onMounted(async () => {
  try {
    const res = await fetch('/api/v1/rounds')
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
    payload.value = await res.json()
    mode.value = 'live'
  } catch (e) {
    error.value = String(e)
    mode.value = 'error'
  }
})

function fmtValue(v: number): string {
  return v >= 1 ? v.toFixed(3) : (v * 100).toFixed(1) + '%'
}

function closedRounds(): Round[] {
  return (payload.value?.rounds ?? []).filter(r => r.division === 'CLOSED')
}

function openRounds(): Round[] {
  return (payload.value?.rounds ?? []).filter(r => r.division === 'OPEN')
}
</script>

<template>
  <section class="lr-board" aria-labelledby="lr-board-title">
    <header class="lr-board-head">
      <h2 id="lr-board-title">Leaderboard Rounds</h2>
      <p class="lr-board-subtitle">Versioned ranked rounds per division · governed by the leaderboard-round contract</p>
    </header>

    <div v-if="mode === 'loading'" class="lr-state lr-state--loading" aria-live="polite">
      Loading rounds…
    </div>

    <div v-if="mode === 'error'" class="lr-state lr-state--error" role="alert">
      Could not load rounds: {{ error }}
    </div>

    <template v-if="mode === 'live' && payload">

      <!-- CLOSED division -->
      <section v-if="closedRounds().length" class="lr-division lr-division--closed">
        <div class="lr-division-head">
          <h3>CLOSED division <span class="lr-badge lr-badge--closed">comparable</span></h3>
          <p class="lr-division-note">Strict apples-to-apples: same benchmark, same division. Ranks are directly comparable.</p>
        </div>

        <article v-for="round in closedRounds()" :key="round.round_id + round.version" class="lr-round">
          <div class="lr-round-head">
            <span class="lr-round-id">{{ round.round_id }}</span>
            <span class="lr-round-version">{{ round.version }}</span>
            <span v-if="round.published_at" class="lr-round-date">{{ round.published_at.slice(0, 10) }}</span>
          </div>
          <p class="lr-round-meta">
            Rank by <strong>{{ round.ranking_rule.metric_id }}</strong>
            ({{ round.ranking_rule.direction === 'higher_is_better' ? '↑ higher is better' : '↓ lower is better' }}) ·
            {{ round.ranking_rule.mode }}
          </p>

          <ol class="lr-entry-list" :aria-label="`${round.round_id} entries`">
            <li v-for="entry in round.entries" :key="entry.entry_id" class="lr-entry">
              <span v-if="entry.rank" class="lr-entry-rank">#{{ entry.rank }}</span>
              <span v-else-if="entry.tier" class="lr-entry-tier">{{ entry.tier }}</span>
              <span class="lr-entry-candidate">{{ entry.candidate_id }}</span>
              <strong class="lr-entry-value">{{ fmtValue(entry.headline.value) }}</strong>
              <span class="lr-entry-metric">{{ entry.headline.metric_id }}</span>
              <span v-if="entry.recipe_proof_ref" class="lr-entry-proof" title="RecipeProof attached">
                ⚗ {{ entry.recipe_proof_ref.recipe_proof_id }}
              </span>
              <span v-if="entry.doi_ref?.version_doi" class="lr-entry-doi" title="DOI">
                DOI: {{ entry.doi_ref.version_doi }}
              </span>
            </li>
          </ol>
        </article>
      </section>

      <!-- OPEN division -->
      <section v-if="openRounds().length" class="lr-division lr-division--open">
        <div class="lr-division-head">
          <h3>OPEN division <span class="lr-badge lr-badge--open">⚠ not comparable to CLOSED</span></h3>
          <p class="lr-division-note">{{ payload.non_comparable_warning }}</p>
        </div>

        <article v-for="round in openRounds()" :key="round.round_id + round.version" class="lr-round">
          <div class="lr-round-head">
            <span class="lr-round-id">{{ round.round_id }}</span>
            <span class="lr-round-version">{{ round.version }}</span>
            <span v-if="round.published_at" class="lr-round-date">{{ round.published_at.slice(0, 10) }}</span>
          </div>
          <p class="lr-round-meta">
            Rank by <strong>{{ round.ranking_rule.metric_id }}</strong> ·
            {{ round.ranking_rule.mode }}
          </p>

          <ul class="lr-entry-list" :aria-label="`${round.round_id} entries (OPEN — not comparable)`">
            <li v-for="entry in round.entries" :key="entry.entry_id" class="lr-entry lr-entry--open">
              <span v-if="entry.tier" class="lr-entry-tier">{{ entry.tier }}</span>
              <span class="lr-entry-candidate">{{ entry.candidate_id }}</span>
              <strong class="lr-entry-value">{{ fmtValue(entry.headline.value) }}</strong>
              <span class="lr-entry-metric">{{ entry.headline.metric_id }}</span>
              <span v-if="entry.recipe_proof_ref" class="lr-entry-proof" title="RecipeProof attached">
                ⚗ {{ entry.recipe_proof_ref.recipe_proof_id }}
              </span>
              <span v-if="entry.doi_ref?.version_doi" class="lr-entry-doi" title="DOI">
                DOI: {{ entry.doi_ref.version_doi }}
              </span>
            </li>
          </ul>
        </article>
      </section>

      <!-- Non-claims -->
      <footer class="lr-nonclaims">
        <strong>Non-claims:</strong>
        <ul>
          <li v-for="nc in payload.non_claims" :key="nc">{{ nc }}</li>
        </ul>
        <p class="lr-source">Source: {{ payload.source }}</p>
      </footer>

    </template>
  </section>
</template>

<style scoped>
.lr-board { display: flex; flex-direction: column; gap: 1.5rem; }
.lr-board-head h2 { margin: 0 0 0.25rem; font-size: 1.25rem; }
.lr-board-subtitle { margin: 0; color: var(--sp-text-muted, #888); font-size: 0.875rem; }
.lr-state { padding: 1rem; border-radius: 6px; }
.lr-state--loading { color: var(--sp-text-muted, #888); }
.lr-state--error { background: var(--sp-error-bg, #fee); color: var(--sp-error-fg, #c00); }
.lr-division { display: flex; flex-direction: column; gap: 1rem; }
.lr-division-head h3 { margin: 0 0 0.25rem; font-size: 1rem; display: flex; align-items: center; gap: 0.5rem; }
.lr-division-note { margin: 0; font-size: 0.8125rem; color: var(--sp-text-muted, #888); }
.lr-badge { font-size: 0.7rem; font-weight: 600; padding: 1px 6px; border-radius: 4px; }
.lr-badge--closed { background: var(--sp-success-bg, #e6f4ea); color: var(--sp-success-fg, #1a7340); }
.lr-badge--open { background: var(--sp-warn-bg, #fef7e0); color: var(--sp-warn-fg, #7d4e00); }
.lr-round { padding: 0.75rem; border: 1px solid var(--sp-border, #e0e0e0); border-radius: 8px; }
.lr-round-head { display: flex; align-items: baseline; gap: 0.5rem; margin-bottom: 0.25rem; }
.lr-round-id { font-weight: 700; font-size: 0.9375rem; }
.lr-round-version { font-size: 0.8125rem; color: var(--sp-text-muted, #888); }
.lr-round-date { font-size: 0.8125rem; color: var(--sp-text-muted, #888); margin-left: auto; }
.lr-round-meta { margin: 0 0 0.75rem; font-size: 0.8125rem; }
.lr-entry-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.375rem; }
.lr-entry { display: flex; align-items: baseline; gap: 0.5rem; font-size: 0.875rem; padding: 0.25rem 0; border-bottom: 1px solid var(--sp-divider, #f0f0f0); }
.lr-entry:last-child { border-bottom: none; }
.lr-entry--open { opacity: 0.9; }
.lr-entry-rank { font-weight: 700; min-width: 2ch; color: var(--sp-accent, #1a56db); }
.lr-entry-tier { font-size: 0.75rem; padding: 1px 5px; border-radius: 4px; background: var(--sp-muted-bg, #f5f5f5); }
.lr-entry-candidate { flex: 1; font-weight: 500; }
.lr-entry-value { font-variant-numeric: tabular-nums; color: var(--sp-accent, #1a56db); }
.lr-entry-metric { font-size: 0.75rem; color: var(--sp-text-muted, #888); }
.lr-entry-proof { font-size: 0.75rem; color: var(--sp-success-fg, #1a7340); }
.lr-entry-doi { font-size: 0.7rem; color: var(--sp-text-muted, #888); }
.lr-nonclaims { padding: 0.75rem; background: var(--sp-muted-bg, #f5f5f5); border-radius: 6px; font-size: 0.8125rem; }
.lr-nonclaims ul { margin: 0.25rem 0 0.5rem 1.25rem; padding: 0; }
.lr-source { margin: 0; color: var(--sp-text-muted, #888); }
</style>
