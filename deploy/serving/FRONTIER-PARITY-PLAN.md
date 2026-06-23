# Frontier-parity run — the plan (the actual number)

Goal: produce **the real number** — our GPU mesh vs Claude/GPT on the same
problems, graded by independent hidden tests, **persisted as reproduced
evidence** (`competitor_snapshots.reproduced_by_us=true`), then torn down.

`deploy/serving/README.md` is the happy-path motion. This plan fills the gaps it
glosses (the persist path) and surfaces the decisions to make before we spend.

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
4. create secret frontier-keys (ANTHROPIC_API_KEY + OPENAI_API_KEY)
5. kubectl apply head-to-head-job.yaml  (POSTGRES_DSN + MESH_URL in-cluster + keys)
6. logs -f → scores; curl /v1/competition/reproduced-vs-claimed | jq  → the number + evidence
7. kubectl delete mesh-vllm-serve.yaml + the job + (optionally) the cluster   # stop GPU bill
```

## Decisions to make (before we spend)
1. **Problem bank size — the big one.** The bank is **8 problems** today → any
   number is *directional/anecdotal*, not a defensible parity claim. Options:
   (a) run the 8 now for a live-mechanism number; (b) expand the bank first
   (HumanEval/MBPP subset or more hidden-test problems → 50–100) for a number
   that holds up. Recommend (b) if the number is going to a client; (a) if it's
   an internal smoke.
2. **Mesh model / GPU.** Default `Qwen/Qwen2.5-Coder-7B-Instruct` on **L4**
   (quota 8, fits 24 GB). Bigger model → A100 (~10× cost). Recommend L4/7B.
3. **Frontier arms.** Defaults `claude-sonnet-4-6` + `gpt-4o`. Confirm models.
   **Need the keys** — provided as the `frontier-keys` secret. Do we have them?
4. **Persist?** Yes → the evidence/reproduced-vs-claimed story (the moat). Needs
   steps 1–2. `--no-persist` skips postgres but you only get printed scores.
   Recommend persist.
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
