# Reusable internal-model register (top-15)

The shelf of common analytical models every business needs — as **governed** Crystal Atlas
`analytic-model-catalog-entry.v0` families. Companion to
[corporate-intelligence-plane](./corporate-intelligence-plane.md) (#1284) and the capability matrix
(#1285). Source of truth: [`contracts/crystal-atlas/registry/internal-models.v0.json`], validated by
`tools/validate_internal_models_register.py` (run in CI).

**Discipline:** every model is a governed artifact (admissibility + provenance). Per the
effect-canary rule, a model is `verified` **only** when a named eval fixture passes — a card without
one is never silently trusted. Today **verified = 0/15**: even the models we HAVE lack governed eval
fixtures. That is the honest starting line, not a failure to hide.

| # | Model | Family / task | Status | Realizing component | Output contract |
|---|---|---|---|---|---|
| 1 | Fraud / anomaly detection | fraud / anomaly | 🔴 GAP | — | `risk.anomaly.flagged.v0` (proposed) |
| 2 | Next-best-action / next-best-offer | recommender / ranking | 🔴 GAP | — | `action.next_best.recommended.v0` (proposed) |
| 3 | Collaborative-filtering recommender (CoRE / co-clustering) | recommender / ranking | 🔴 GAP | — | `offering.recommended.v0` (proposed) |
| 4 | Churn / attrition | predictive / classification | 🔴 GAP | — | `churn.risk.scored.v0` (proposed) |
| 5 | Propensity / lead & opportunity scoring | predictive / classification | 🟡 PARTIAL | crystal-atlas-contract-intel | `intel.value_driver.scored.v0` ✅ |
| 6 | Segmentation & clustering | predictive / clustering | 🔴 GAP | — | `segment.assigned.v0` (proposed) |
| 7 | Customer lifetime value (CLV) | predictive / regression | 🔴 GAP | — | `clv.estimated.v0` (proposed) |
| 8 | Demand / revenue forecasting | forecasting | 🔴 GAP | — | `forecast.timeseries.emitted.v0` (proposed) |
| 9 | **Credit / counterparty risk** (PD·LGD·EAD → EL, econ-capital, RORAC) | risk / regression | 🟡 PARTIAL | crystal-atlas-contract-intel | `diligence.risk.pack.generated.v0` ✅ |
| 10 | Price / offer optimization (risk-adjusted, FTP) | pricing / optimization | 🔴 GAP | — | `price.optimized.v0` (proposed) |
| 11 | Sentiment / stance / topic | nlp / classification | 🔴 GAP | — | `text.sentiment.classified.v0` (proposed) |
| 12 | Entity resolution / identity matching | resolution / matching | 🟢 HAVE | entity-resolution | `catalog.resolved.v0` ✅ |
| 13 | Semantic search & retrieval ranking | retrieval | 🟢 HAVE | sherlock-engine | — (results, not a fact) |
| 14 | Document intelligence / extraction | extraction | 🟢 HAVE | nugget-extractor | `doc.clauses.extracted.v0` ✅ |
| 15 | Skills / talent matching | matching | 🔴 GAP | — | `skill.match.scored.v0` (proposed) |

## Financial-risk decomposition (models #9, #10)

Model #9 is the load-bearing one for financial services: **Expected Loss = PD × LGD × EAD**, rolling
up to **economic capital**, **RORAC**, and the **economic-profit** framework
(EP = Revenue − EL − Expenses − Funding Costs + Funding Credits − Taxes − Capital Charge). Model #10
(pricing) carries **funds-transfer-pricing (FTP)** + risk-adjusted / hurdle-rate pricing. These are
prime candidates for the interactive-visualization wave (Bostock/NYT-style calculators) — a PD·LGD·EAD
→ EL / economic-capital explorer, an FTP calculator, a recovery-rate / credit-VaR visualizer.

## Grounding

Register + validator (this PR) is the coherence artifact. Gap models grounded as issues (umbrella +
high-value decisioning models). Deduped against existing model-catalog / entity-resolution /
retrieval issues (not re-filed). Next-most-valuable step per gap: attach a governed eval fixture so a
model can move from HAVE/PARTIAL → **verified**.
