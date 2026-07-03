# Ray LoRA loop — stage 1: the training execution

The platform declared Ray as its training standard (`RAY_RUNTIME_REF = runtime-asset:prophet-ray-ml`,
role `ray-train`) across lattice-studio and eval-fabric, and defined the promotion/rollback gates —
but nothing ever **ran** a fine-tune. This is that missing muscle: a KubeRay **RayJob** that
LoRA-fine-tunes a base model on rejection-sampled **verified traces**, on an **ephemeral** GPU
cluster that tears itself down.

This is stage 1 of the compounding loop. The full loop:

```
harvest verified traces (noetica)  →  /api/tune submit  →  [THIS: Ray LoRA train]
   →  promotion gate (head-to-head base vs base+adapter, promote-never-demote)
   →  serve (vLLM --enable-lora) + model-zoo register  →  sharper model  →  repeat
```

## Files
| File | Purpose |
| --- | --- |
| `ray_lora_train.py` | Ray Train (`TorchTrainer`) + peft LoRA. Reads verified SFT JSONL → adapter → optional GCS. |
| `lora-rayjob.yaml` | KubeRay `RayJob` — ephemeral cluster, GPU worker, `shutdownAfterJobFinishes`. |
| `sample.sft.jsonl` | 3-line sample for the local smoke test. |

## One-time: install the KubeRay operator (the Ray substrate)

```bash
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm install kuberay-operator kuberay/kuberay-operator --version 1.2.2 -n ray-system --create-namespace
```

## Run a training job

```bash
# 1. ship the training script as a ConfigMap (source of truth stays ray_lora_train.py)
kubectl -n training create configmap ray-lora-script \
    --from-file=deploy/training/ray-lora/ray_lora_train.py

# 2. (the SFT shard of verified traces is staged into the head's /home/ray/data by the submit step)

# 3. launch — GPU worker auto-provisions, trains, uploads the adapter, cluster self-deletes
kubectl apply -f deploy/training/ray-lora/lora-rayjob.yaml
kubectl -n training get rayjob lora-verified -w
kubectl -n training logs -l ray.io/job-name=lora-verified -f
```

The adapter lands at `ADAPTER_GCS` (default `gs://noetica-brains/adapters/lora-verified`) for the
promotion gate (stage 3) and serving (`mesh-vllm --enable-lora`, stage 4).

## Cost discipline
`shutdownAfterJobFinishes: true` deletes the GPU worker the instant the job ends — the GPU bills
only for the run. Nothing standing.

## Local smoke test ($0, no GPU, no cloud)

The script runs in Ray local mode on CPU with a tiny base model — proves the train path end to end:

```bash
cd deploy/training/ray-lora
pip install "ray[train]" torch transformers peft datasets accelerate
BASE_MODEL=sshleifer/tiny-gpt2 RAY_USE_GPU=0 EPOCHS=1 \
    SFT_PATH=sample.sft.jsonl ADAPTER_OUT=/tmp/adapter \
    python ray_lora_train.py
# → "RAY LORA DONE ... adapter=/tmp/adapter"  and a PEFT adapter on disk
```

Validate the manifest before applying:

```bash
kubectl apply --dry-run=client -f deploy/training/ray-lora/lora-rayjob.yaml   # needs KubeRay CRDs
```
