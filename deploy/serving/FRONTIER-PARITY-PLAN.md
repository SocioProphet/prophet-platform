# Frontier-parity run — the plan (the actual number)

Goal: produce **the real number** — our GPU mesh vs Claude/GPT on the same
problems, graded by independent hidden tests, **persisted as reproduced
evidence** (`competitor_snapshots.reproduced_by_us=true`), then torn down.

`deploy/serving/README.md` is the happy-path motion. This plan fills the gaps it
glosses (the persist path) and surfaces the decisions to make before we spend.

## Rule #0 — NO CONTAMINATION (non-negotiable)
The exam proves the **architecture** (the brain + the jujitsu ops), not what any
model memorized. If a score reflects memorization or lookup, it's invalid — "if
there is contamination we're not doing it right." Four hard guards:
1. **Contamination-controlled problem set.** Problems neither our model nor the
   frontier saw in pretraining — i.e. **post-training-cutoff / held-out**.
   Public benchmarks (HumanEval, MBPP) are DISQUALIFIED (memorized). Use
   **LiveCodeBench** (problems dated after model cutoffs, function-level, hidden
   tests, and a public frontier leaderboard → satisfies "vs their *published*
   number" with no live API and no contamination), or a freshly-authored
   held-out set we keep private.
2. **No training on answer keys.** Our training (`deploy/training/*`) never
   touches the exam set or its solutions.
3. **Hellgraph excludes the exam.** The retrieval/KG arm grounds on *general*
   cross-org knowledge only. The exam problems/solutions are NEVER ingested into
   hellgraph — otherwise the "jujitsu" is just answer lookup. Enforced by an
   explicit exclusion guard + an assertion in the run.
4. **Hidden tests stay hidden.** Graded after generation, never in the prompt
   (the runner already separates `prompt` from `test` — keep it that way).

A clean result = our architecture closing the gap to the frontier's *published*
number on problems nobody trained on. That's the only number worth showing.

## Already proven (free, done)
The mechanism works end to end at $0: 6/6 runner unit tests; live `--no-persist`
vs a local mesh scored 3/3 graded by the hidden tests. What's left is the *paid*
part: a real model on a GPU + frontier API calls + persistence.

## What the persisted proof needs (the gap in the README)
The README's step 4 (`curl …/reproduced-vs-claimed`) only works if persistence
landed. That requires three things the README assumes:
1. **Postgres** reachable by the Job, with `infra/datastores/postgres/001…005_*.sql`
   applied (creates `eval_runs`/`trials`/`competitor_snapshots` + the seeded
   `src_internal_eval_runner` source + `ctx_high_assurance_code_agent` slice).
2. **`POSTGRES_DSN`** wired into `head-to-head-job.yaml` (and into eval-fabric-api).
3. **eval-fabric-api** running, to *read back* the reproduced-vs-claimed view
   (or query postgres directly).

## Sequence (≈30–45 min, one teardown)
```
0. tofu apply gcp-gke         # cluster (~13 min); get-credentials
1. postgres + schema          # kubectl apply a postgres pod; psql -f 001..005_*.sql
2. eval-fabric-api            # deploy it pointed at POSTGRES_DSN (Argo or kubectl)
3. kubectl apply mesh-vllm-serve.yaml; rollout status --timeout=15m   # L4, ~5–15 min model load
4. seed published-leaderboard numbers (the "claimed" side) — NO live frontier API
5. kubectl apply head-to-head-job.yaml  (POSTGRES_DSN + MESH_URL in-cluster + exam slice)
6. logs -f → scores; curl /v1/competition/reproduced-vs-claimed | jq  → the number + evidence
7. kubectl delete mesh-vllm-serve.yaml + the job + the ephemeral DB + the cluster   # stop all spend
```

## Locked decisions (per the no-handicap / no-contamination direction)
1. **Exam set — contamination-controlled, n≥30 (target 100+).** Reflect the real
   exams, but only ones nobody trained on (see Rule #0). **LiveCodeBench**
   (post-cutoff, hidden tests, public frontier leaderboard) is the fit; we take a
   slice of n≥30–100. Hand-written-8 stays only as the $0 smoke. 8 is not a
   statistically normal set — we don't ship it as the number.
2. **Mesh model — SOTA, no handicap.** A big open model on **multi-A100 (spot,
   quota 16)** — e.g. `Qwen2.5-Coder-32B-Instruct` (2×A100-40, tensor-parallel-2)
   or a 70B (4×A100). No 7B/L4 handicap — if we spin up cloud to fight the
   frontier, we field a real model. Plus **hellgraph** (cross-org/enterprise KG)
   grounding + verify-repair = the full "brain + jujitsu" arm.
3. **Frontier comparison — published numbers, NOT their services.** No live
   Claude/GPT API calls. The "claimed" side = their **published per-model
   leaderboard score on the SAME contamination-controlled benchmark**, seeded
   into `competitor_snapshots`. Drop the live `claude`/`gpt` arms from the runner.
4. **Persist — yes**, the reproduced-vs-claimed evidence is the point.
5. **DB — ephemeral.** Stand up, prove, tear down; nothing left billing.
5. **Postgres source.** A throwaway **pod** (cheapest, teardown-clean) vs Cloud
   SQL. Recommend a pod for the demo.

## Cost (rough, one run)
- L4 GPU ~$0.70/hr × ~0.75 hr ≈ **$0.50**
- Cluster Autopilot for the window ≈ cents
- Frontier tokens: 8 problems × 2 models ≈ **$0.10–0.50** (more if the bank grows)
- Postgres pod ≈ free
- **Total ≈ $1–2** for the 8-problem run; scales with bank size + token use.

## Honest strength note
With 8 problems this is a *live demonstration that our mesh reproduces frontier
results on graded problems*, not a statistically strong parity benchmark.
Expanding the bank (decision 1b) is what turns "look, it matches" into "here's
the measured parity number." Either is real; be clear which we're claiming.

## Risks / mitigations
- vLLM first-load downloads ~15 GB (Qwen-7B) → 5–10 min; `hf-cache` volume helps on retry. 8192 ctx + 0.92 mem-util fits L4.
- eval-fabric schema/seed must be applied or persist fails → step 1 is mandatory for the persisted claim.
- Frontier rate limits: negligible at 8 problems.
- Teardown discipline: the GPU node is the only standing cost — `kubectl delete` the serving Deployment the moment we're done (step 7).
