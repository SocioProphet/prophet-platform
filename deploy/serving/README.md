# Cloud-mesh proof — serving + live head-to-head

The capability to **walk into a client, spin up our own GPU mesh, and prove it matches the frontier
labs with our own live tests** — and land that proof in the governance layer (eval-fabric) as a
reproduced fact, not a hardcoded reference.

This directory is the piece the platform was missing. Everything else already existed:

| Already in the platform | Where |
| --- | --- |
| GCP/AWS/IBM GPU node pools (IaC) | `infra/tofu/environments/*` |
| GPU training + LoRA Jobs | `deploy/training/*` |
| eval-fabric **reporting** (`/v1/competition/reproduced-vs-claimed`, `/radar`, dossiers, receipts) | `apps/eval-fabric-api` |

What was missing — and is added here:

| New | What it does |
| --- | --- |
| `mesh-vllm-serve.yaml` | GPU **inference serving** — an open model on an OpenAI-compatible endpoint (the "cloud mesh") |
| `head-to-head-job.yaml` | runs the live comparison and **writes** the reproduced evidence |
| `app/runner/head_to_head.py` | the runner: mesh + verify-repair vs Claude/GPT, hidden-test-graded, persists `competitor_snapshots` |

## The demo motion

```bash
# 1. SPIN UP the mesh (GPU node auto-provisions on the existing pools). ~5–15 min first time.
kubectl apply -f deploy/serving/mesh-vllm-serve.yaml
kubectl -n serving rollout status deploy/mesh-vllm --timeout=15m

# 2. (optional) arm the frontier — without this, only the sovereign arms run + get recorded
kubectl -n prophet-platform create secret generic frontier-keys \
    --from-literal=anthropic=$ANTHROPIC_API_KEY --from-literal=openai=$OPENAI_API_KEY

# 3. PROVE — run the head-to-head; it grades live and persists reproduced_by_us=true rows
kubectl apply -f deploy/serving/head-to-head-job.yaml
kubectl -n prophet-platform logs -f job/head-to-head-proof

# 4. SHOW the client the reproduced evidence (with provenance + evidence receipts)
curl http://eval-fabric-api:8080/v1/competition/reproduced-vs-claimed | jq

# 5. TEAR DOWN — the GPU bills only while the Deployment is up. Do this the moment you're done.
kubectl delete -f deploy/serving/mesh-vllm-serve.yaml
kubectl -n prophet-platform delete job head-to-head-proof
```

## Cost discipline (read before you apply)

- The **only** paid resource is the GPU node behind `mesh-vllm`. It exists only between step 1 and
  step 5 — `kubectl delete` scales the node pool back to zero. Nothing here runs standing.
- Frontier arms cost per-token API spend (a few cents for the 8-problem suite). The sovereign arms
  are free once the node is up.
- Pick the GPU to the model: `nvidia-tesla-t4` (cheapest) for ≤3B, `nvidia-l4` (default) for 7B,
  `nvidia-tesla-a100` for 30B+. Edit `nodeSelector` + `MESH_MODEL` together.

## Local dry-run (no cloud, no spend)

The runner is fully testable without a GPU — point it at any OpenAI-compatible endpoint (a local
Ollama, vLLM, etc.) and skip persistence:

```bash
cd apps/eval-fabric-api
MESH_URL=http://127.0.0.1:11435/v1 MESH_MODEL=qwen2.5-coder:7b \
  python -m app.runner.head_to_head --limit 3 --no-persist
```

Validate the manifests before applying:

```bash
kubectl apply --dry-run=client -f deploy/serving/mesh-vllm-serve.yaml
kubectl apply --dry-run=client -f deploy/serving/head-to-head-job.yaml
```
