# Platform-feature proof — model training & finetuning

Demonstrates the platform can run **GPU model training** and **LLM finetuning**
as first-class workloads. Self-contained Jobs: public PyTorch image + embedded
scripts, so it's one `kubectl apply` each — no image to build.

On GKE Autopilot the `nvidia.com/gpu` request **auto-provisions a GPU node**
(scales away after, via `ttlSecondsAfterFinished`). Same manifests run on
AKS/EKS/IKS — their GPU pools are pre-defined in the substrate envs.

## One-shot demo (tomorrow)

```sh
# 1. stand the cluster back up (was torn down for cost)
cd infra/tofu/environments/gcp-gke && tofu apply        # ~13 min
$(tofu output -raw get_credentials)

# 2. model training proof
kubectl apply -f deploy/training/gpu-train-job.yaml
kubectl logs -f job/gpu-train -n training
#   → device: Tesla T4 ... loss decreasing ... TRAINING OK

# 3. LoRA finetuning proof
kubectl apply -f deploy/training/lora-finetune-job.yaml
kubectl logs -f job/lora-finetune -n training
#   → trainable params ... train loss ... LoRA FINETUNE complete
```

## What each proves
- `gpu-train-job.yaml` — a real gradient-descent training loop on a GPU; asserts CUDA is present, loss converges, checkpoint saved. Fast + deterministic.
- `lora-finetune-job.yaml` — LoRA finetune of a tiny causal LM on a small corpus; trainable-param report, decreasing train loss, adapter saved. The finetuning path.

## Notes
- First GPU pod waits ~2–4 min for Autopilot to provision the node.
- These prove the capability; production training would build a dedicated image (pinned deps, dataset from GCS, checkpoints to GCS) and run as an Argo Workflow / Job in the `socioprophet` namespace.
- GPU type `nvidia-tesla-t4` (cheapest). Bump the nodeSelector for bigger jobs.
