# Web Intelligence lane — platform contracts

Governed, contract-first event schemas for the **Web Intelligence** lane of the
intelligence program. This lane evaluates industry-standard web-intelligence
metrics — the kind vendors like Semrush charge for — **for our own domains and
for competitors, symmetrically**, and emits every metric as a governed claim.

We do not consume a vendor here. This lane is the specification for our own
owned engine (crawler + AI-visibility probes + SERP probes). Vendor tools are
the *bar*, not a dependency.

## What makes this beat the industry bar

Every event carries the same **warrant envelope** — so a competitor metric is as
auditable as one about ourselves:

- `subject` — the domain evaluated (ours or a competitor's).
- `relation` — `self | competitor | prospect | partner` (the lane is symmetric).
- `epistemic_level` — `proved | bounded | empirical | synthetic | speculative | rejected`.
- `provenance` — `source` (`owned_crawler | ai_probe | serp_probe | link_graph`),
  `method`, `sample_size`, `collected_at`.

Two differentiators the standard vendors do not offer:

1. **AI-search-native** — `webintel.ai_visibility.probed.v0` measures visibility
   and citation across ChatGPT, Perplexity, Google AI, Gemini, and Grok.
2. **Warranted + composable** — the scorecard's `overall_epistemic_level` is the
   **meet** of its component levels (one weak input caps the whole), and it
   carries a **value-driver** breakdown so intel findings arrive with quantified,
   equity-weighted impact rather than raw numbers.

## Event families

### Upstream (owned-engine measurements)
- `webintel.site_audit.completed.v0`
- `webintel.backlink_profile.assessed.v0`
- `webintel.ai_visibility.probed.v0`
- `webintel.serp_rank.tracked.v0`
- `webintel.content_gap.analyzed.v0`

### Downstream (synthesis)
- `webintel.scorecard.generated.v0`

## Notes

Contract-first: schemas land before runtime. The deployable consumer is
`apps/web-intel-metrics`; schemas are validated by
`tools/validate_web_intel_contracts.py` against the committed examples.
