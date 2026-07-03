# Wave 3 — elastic scale (spin up / spin down)

Autoscaling + scale-to-zero + ephemeral environments — the cost-bounded elasticity
of the E2E plan. Scales on the Wave-1 Prometheus metrics.

## Scale-to-zero for GPU serving (`keda-scaledobject-vllm.yaml`) — **deploys**

KEDA scales `mesh-vllm` (the GPU serving Deployment) **0 → N on request load** and
back to **0** after a 5-minute idle cooldown. This makes automatic the cost
discipline the serving manifest asks for ("the GPU bills only while a replica is
ready"). Trigger reads the Wave-1 Prometheus.

## Reference patterns (examples — adopt per service)

- **`hpa-example.yaml`** — CPU HPA for stateless services (min 2 / max 10 @ 70%).
- **`keda-scaledjob-eval.example.yaml`** — the **frontier-parity / head-to-head
  eval** as a self-terminating GPU `ScaledJob`: provisions a GPU pod on a trigger,
  runs, lets the node scale back to zero (GPU pools are `min=0` in Tofu). Cost
  bounded to the run.

## Ephemeral preview envs (`infra/argocd/preview-envs-appset.yaml`)

An ApplicationSet **PullRequest generator**: every PR labelled `preview` gets its
own `pr-<N>` namespace + Application; when the PR closes it drops out of the
generator and is **pruned automatically**. Spin-up and spin-down with no manual
cleanup, opt-in so cost stays bounded.

## Install (`infra/argocd/autoscaling-stack.yaml`)

`keda` (wave -2) → `autoscaling-base` (wave 0, the vLLM ScaledObject).

## Needs a live cluster

- HPA needs `metrics-server`; KEDA Prometheus triggers need Wave-1 Prometheus.
- Metric names in triggers assume OTel HTTP semconv — confirm on first deploy.
- Chart pinned (keda 2.15.1).
