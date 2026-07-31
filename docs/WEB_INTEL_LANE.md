# Web Intelligence lane

The Web Intelligence lane makes industry-standard web-intelligence metrics — the
kind vendors like Semrush sell — a **first-class, owned capability of the
intelligence program**, evaluable **for our own domains and for competitors**,
with every metric emitted as a governed claim.

We do not consume a vendor. Vendor tooling is the *bar* we match and beat.

## Where it sits

Third lane of the intelligence program, alongside:

1. **Contract / competitive intel** — Crystal Atlas (`contracts/crystal-atlas`, `apps/crystal-atlas-contract-intel`).
2. **Value-driver / valuation** — the value-projection tooling.
3. **Web intelligence** — this lane (`contracts/web-intel`, `apps/web-intel-metrics`).

The scorecard integrates the value-driver mechanism directly: each web-intel
dimension is mapped to a driver with an equity-weighted impact score, so
findings arrive quantified rather than raw.

## Owned engine (the sources behind the metrics)

- **owned_crawler** — Playwright/Scrapy + lxml + simhash/minhash → site health,
  crawl buckets, duplicate/thin detection, internal-link graph, control files.
- **link_graph** — owned crawl merged with Common Crawl → backlink profile,
  toxicity, anchor concentration, authority, disavow candidates.
- **serp_probe** — owned SERP fetch → rank, share-of-voice, content gaps.
- **ai_probe** — five-engine citation probe (ChatGPT, Perplexity, Google AI,
  Gemini, Grok) → AI-search visibility. This is the axis standard vendors miss.

## How it beats the bar

- **Symmetric.** Every event carries `subject` + `relation` (`self | competitor |
  prospect | partner`); a competitor metric is as first-class and auditable as
  one about ourselves.
- **Warranted.** Every metric carries `epistemic_level` + `provenance`
  (source/method/sample_size/collected_at). The scorecard's
  `overall_epistemic_level` is the **meet** of its components — one weak input
  caps the whole.
- **AI-search-native.** First-class visibility across five generative engines.
- **Composable.** Scorecards feed the value-driver breakdown and the broader
  intelligence program on one evidence spine.

## Event families

Upstream: `webintel.site_audit.completed.v0`,
`webintel.backlink_profile.assessed.v0`, `webintel.ai_visibility.probed.v0`,
`webintel.serp_rank.tracked.v0`, `webintel.content_gap.analyzed.v0`.

Downstream: `webintel.scorecard.generated.v0`.

## Runtime

- Service: `apps/web-intel-metrics` (FastAPI). Endpoints under `/v1/web-intel`.
- Emitter: `tools/emit_web_intel_scorecard.py` synthesizes a governed scorecard
  from component metric events and writes it to the state spine.
- Validation: `tools/validate_web_intel_contracts.py` checks every schema and
  its committed example (the lane CI gate).
