# Credit-risk & economic-capital visualization wave

Interactive, reproducible-from-source explanatory visualizations for the profit-and-risk domain —
Bostock / NYT-mortgage-calculator caliber. Self-contained HTML/SVG/Canvas, theme-aware, accessible.
**No captured third-party images or branding** (the McKinsey/BIS/OCC figures are reference only) —
per the estate "diagram is a witness" rule.

| File | What it is |
|---|---|
| `credit-risk-thesis.html` | 12-module thesis — EL calculator, **Vasicek Monte-Carlo portfolio-loss simulation**, risk measures (VaR/ES/σ/spectral + coherence), regulatory-vs-economic capital stack, EP & EP-variance waterfalls, matched-maturity FTP, recovery-by-seniority + PD↔RR, EAD race-to-default, risk-aggregation diversification, DCF life-cycle fade, credit-model taxonomy. |
| `profit-risk-drilldown.html` | Economic-Profit & RAROC drilldown — additive roll-up Firm→LOB→Segment→Product→Client→Transaction, EP-variance waterfall, economic-capital loss distribution. |

## The Bostock interaction model (how these are built)

1. **Direct manipulation, immediate feedback.** Every input is a slider or a click; the model recomputes
   live (a shared five-lever portfolio — PD, LGD, EAD, ρ, confidence — flows through EL → simulation →
   risk measures → capital, so one gesture ripples across screens). No "apply" button.
2. **Teach by manipulating, not by captioning.** The lesson is in what moves: raise ρ and the loss tail
   visibly fattens while the mean holds — you *see* why correlation, not average PD, drives capital.
3. **No chart-junk.** Recessive grid/axes, thin marks, direct labels over legends, one idea per view.
4. **Honest by construction.** Illustrative data is labeled as such; the math is real (Vasicek single-factor,
   Ninv/normal-CDF, Monte-Carlo over 6k economies). Colorblind-safe: blue/orange not red/green; status
   carries icon + label; palette validated for CVD + contrast in both light and dark.

## Data source (production)

Illustrative defaults today. In production these are **witnesses over governed facts**: PD·LGD·EAD and
the loss tail from `diligence.risk.pack` / internal-model #1293, EP & variance from `economic-prophet`
(as `ep.variance.decomposed.v0`), peer benchmark from the corporate-intelligence plane (#1284) —
surfaced through this `lattice-studio` viz layer and `dashboard-bff`. Wiring tracked in #1294.

## Ross recovery — witness over economic-prophet

The **Ross recovery & curves** module ports `economic-prophet/src/open_ep_framework/recovery.py` **exactly** (`planning_recovery` RR^P, `market_implied_recovery` RR^Q, `recovery_wedge` ΔRR) — product_spec §6 (Ross / Arrow-Debreu). On top it runs the actual **Ross Recovery Theorem**: option-implied Arrow-Debreu state prices → the Perron eigenproblem `Pφ = δφ` recovers the real-world measure P and the pricing kernel φ from the risk-neutral Q. It surfaces the futures/forward curve and the option call-price curve, and the values that pop out (real-world vs risk-neutral PD, the risk premium, recovered discount δ). Verified: recovered δ = true discount; risk-neutral PD > real-world PD.

## Alternative inflation — BPP & ShadowStats (witness over economic-prophet)

The **Alternative inflation** module ports `economic-prophet/src/open_ep_framework/inflation.py`: a Billion-Prices-Project chained **Jevons** online-price index and a **ShadowStats** alternate CPI (official + reversed BLS methodology add-backs, 1980/1990 bases), plus the exact-Fisher **real rate** that reprices every book. The vendor series are proprietary (PriceStats commercial, ShadowStats subscription) so the methodologies are **reconstructed** — flagged as such; wire a real feed for the genuine index. economic-prophet PR #40.
