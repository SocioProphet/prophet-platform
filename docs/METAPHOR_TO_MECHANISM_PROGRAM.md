# METAPHOR → MECHANISM: the design-execution program

**Status:** v0 · 2026-07-28 · owner: Michael + agent sessions
**Companion register (machine-checkable):** `docs/design-register.yaml`

## 1. The failure mode this program exists to kill

The estate has a chronic, documented pattern: **designs are authored, sometimes even coded,
and then never wired, never measured, and eventually rediscovered by archaeology.** The
record convicts us repeatedly:

- L5 governance: complete FSM library (`lifecycle.ts`), **zero callers**, CI green throughout.
- Zero-trust: **cosmetic** declarations; enforcement landed only when the
  declared-unenforced register forced it (Wave 1: #116/#563/#205).
- Digital-twin organs: **design-only** while the membrane shipped.
- Wave 0–4 delivery corpus: **authored but stranded** in an unwatched Argo tree.
- Corpus backlog: 13/14 items finished **on uncommitted branches**.
- The concept diagram audited 2026-07-28 (thermodynamic lifecycle, monads, Fourier memory,
  L-function planning, organogenesis): **0% implemented as designed** — its *functions*
  ~70% covered by other mechanisms, its four novel ideas absent entirely.

Root causes, named precisely:

1. **Designs are prose/diagrams — nothing fails when they're ignored.** A YAML value that
   drifts breaks CI; a diagram that drifts breaks nothing.
2. **"Library exists" masquerades as "capability exists."** CI proves code compiles, not
   that anything *calls* it. Zero-caller libraries stay green forever.
3. **Metaphor is never translated to mechanism.** "Organs", "thermodynamics" have no
   greppable referent, so nobody can even *test* whether they shipped.
4. **Client work structurally starves design work.** Sprints fill with ST-items and field
   bugs; design items have no reserved lane, so they lose every priority contest.
5. **Session memory decays.** Agent sessions rediscover state by archaeology and sometimes
   rebuild what exists (reporting-watcher, 2026-07-28) or overclaim what doesn't
   ("signed DMG", same day).

## 2. The countermeasures (each mapped to a root cause)

### C1. The Design Register — designs become machine-checkable state (kills RC1, RC3)
`docs/design-register.yaml`: one entry per design concept. Every entry carries:

```yaml
- id: exhaust-accounting
  source: concept-diagram-2026-07 (thermodynamics panel)
  mechanism: "ExhaustRecord on every compute/compaction; entropy = bytes_in/bytes_out v1"
  owner: agent-machine + compute-gateway
  status: absent          # absent | declared | wired | measured | sealed
  probe: "receipt of a sample compute carries exhaust_sha + bytes_in/bytes_out"
  wave: W6.1
```

**The status ladder is the new definition of done:**
`absent → declared` (spec/schema merged, sourceos-spec first) → `wired` (**callers > 0,
deployed**, probe passes against the live system) → `measured` (a bench arm or metric
exists and has produced a number) → `sealed` (the number is receipted/replay-exact).
Nothing may be described — in memory, in a retro, to Gus — above its probe-verified status.
This is the declared-unenforced register turned on ourselves.

### C2. Conformance probes in CI (kills RC2)
Extend the existing `diagnostics-gate`: every register entry with status ≥ `wired` has its
probe executed (an HTTP check, a callers-grep, a receipt-field assertion). A probe that
fails **flips the entry red and fails the gate** — "zero callers" becomes a build-visible
state instead of an archaeology finding. Probes are cheap by construction (curl/grep/jq),
runnable locally and in CI identically.

### C3. The reserved design lane (kills RC4)
Standing sprint rule: **every sprint carries exactly one design-register item as a P1**,
sized to the thin-slice pattern that demonstrably lands (ST028: thin slice → bench-proven →
shipped → hardened). One per sprint, never zero, never three. Client STs keep priority for
everything else; this lane is not negotiable away because it is small by design.

### C4. Register-first memory discipline (kills RC5)
The register is the source of truth for "what exists"; agent memory carries a pointer, not
a copy. Sessions verify against probes, not recollection. (Two same-day incidents make
this non-optional: the rebuilt watcher, the "signed" DMG.)

## 3. The implementation plans — augmenting what exists (never greenfield)

Doctrine for all five: **metaphor → mechanism → measurement.** Each design concept is
re-expressed as a mechanism over *existing* estate capabilities, with a probe and a metric.
Research-grade interpretations are explicitly gated behind the v1 mechanism's numbers.

### D1 · Exhaust & entropy accounting (thermodynamics panel) — Wave 6.1
- **Function the metaphor wants:** know what the system *discards*, and learn from it.
- **Mechanism:** every compute/compaction emits an `ExhaustRecord` — counts + content
  hashes of dropped context (chunks, candidate answers, rejected tool calls) — and the
  Receipt gains optional `exhaust_sha`, `bytes_in`, `bytes_out` (spec PR to sourceos-spec
  first; non-breaking). v1 entropy metric = compression ratio; refinement later.
- **The loop (the diagram's best idea):** the existing idle-time trace-consolidation job
  additionally mines exhaust: *discarded-but-later-needed* detection (a later query needed
  a chunk we dropped) feeds retrieval tuning + SRS. Exhaust→intake, literally.
- **Augments:** receipts spine (now durable), agent-machine context assembly, the
  trace-dream job. **Measured:** discard-recall rate + compression ratio on the Govern
  Proof act.

### D2 · Banded memory (Fourier panel) — Wave 6.2
- **Function:** memory with time-scale structure instead of one flat store.
- **Mechanism v1:** multi-timescale bands — L0 session buffer → L1 daily consolidation →
  L2 weekly canon → L3 permanent — with promotion/decay between bands (the diagram's
  layer-density-over-time, operationalized). Augments agent-memory's existing isolation
  routing + SRS.
- **Research gate (the literal Fourier):** the estate already runs an FNO engine
  (`noetica-operator`, tract/ONNX). Experiment — learn a spectral compression operator
  over session-embedding sequences; run as a **bench arm** against plain embeddings on the
  existing board harness (n≥30/subject, all arms kept). Promote only on a measured win.
- **Measured:** retrieval hit-rate by band; bench-arm comparison.

### D3 · Deliberation-value controller (L-function panels) — Wave 6.3
- **Function:** know when more deliberation stops paying (feedback curve crossing
  emergent return).
- **Mechanism v1:** a `DeliberationController` in the reasoning stack that estimates
  P(correct | features) — agreement-across-samples, operator-fire, retrieval-gate scores,
  all already emitted by the harness — and stops/escalates when marginal
  expected-accuracy-per-token drops below threshold. Calibrated on the **686-question
  board transcripts we already own** (labeled data, zero new spend). Extends
  escalate-only-on-disagreement.
- **Research gate:** an L-function/Dirichlet-series functional form for the value curve is
  a Heller-Winters-lane investigation, entertained only if the calibrated controller shows
  structure worth it.
- **Measured:** cost-per-point (tokens spent per pp gained) on the board — bench arm first,
  server routing second.

### D4 · Organs in the mesh (organogenesis panels) — Wave 6.4
- **Function:** the mesh's capabilities become typed, queryable, eventually dynamic.
- **Mechanism v1 — declared organs:** `Organ{kind: memory|routing|perception|policy,
  members[], capabilities[], health}` as a sourceos-spec type, populated over EXISTING
  services (memory-mesh, zone-router/model-router, ingest/ie-engine, capability membrane)
  and served from the federation plane. The diagram's right column becomes an API and a
  Govern Posture card.
- **v2 — membership dynamics:** nodes join/leave organs by capability + load, using the
  already-shipped admit/writer-key machinery.
- **v3 — differentiation (true organogenesis):** research-gated behind v1/v2 utility.
  This ordering repeats the twin program's membrane-then-organs sequencing deliberately.
- **Measured:** organ API serving >0 organs with live health; organ-routed vs direct
  request latencies.

### D5 · Effect discipline (monads panel) — Wave 6.0 (cheapest, first)
- **Function:** lawful, composable effects.
- **Mechanism:** no monad library. Document the correspondence in canon (receipts≈Writer,
  entitlement/context≈Reader, sessions≈State) and **enforce the one law that matters as a
  property test:** a workflow's composite receipt must equal the fold of its step receipts
  (compositionality). The gateway already produces both sides; the test pins the law.
- **Measured:** the property test in the gateway suite. One PR.

## 4. Sequencing

| Wave | Item | Size | Gate |
|---|---|---|---|
| W6.0 | Register + probes scaffold in diagnostics-gate; D5 property test | days | — |
| W6.1 | D1 exhaust: spec fields → emission → Proof-act surfacing | ~1 sprint lane | spec merged first |
| W6.2 | D2 banded memory v1 (promotion/decay) | ~1 sprint lane | — |
| W6.3 | D3 controller as bench arm (existing transcripts, ~$0) | ~1 sprint lane | bench-proven before routing |
| W6.4 | D4 declared organs v1 (+ Govern card) | ~1 sprint lane | spec merged first |
| R-gates | literal-Fourier memory · L-function form · organ differentiation | research | prior wave's metric |

One lane per sprint (C3). At this cadence the whole diagram is `wired`-or-better in ~5
sprints, with every claim probe-backed — versus the historical alternative: another year
of the diagram being true in pictures only.

## 5. What "not failing again" means, operationally

The program is working iff, at any moment, `design-register.yaml` answers — without
archaeology — *what did we design, what of it runs, what of it is measured, and what is
still a picture?* The register red-lining in CI is the system refusing to let a design rot
silently. That is the entire point: **make unimplemented designs a build failure instead
of a memory.**
