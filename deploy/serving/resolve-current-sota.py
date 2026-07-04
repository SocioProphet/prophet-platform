#!/usr/bin/env python3
"""resolve-current-sota — turn a profile's RESOLVE_* slots into concrete open
models, picked per role by FIT to that role's iron.

For each model in the profile, take its family's `preferred` OPEN list from
prophet-mesh model-task-policy.yaml (ordered = current preference), and choose
the first candidate whose weights fit the role's iron envelope
(params × bytes/param(quant) × overhead ≤ gpus × GPU-VRAM × util). Emit a
resolved profile + a resolution receipt (the evidence: what, why, fit math).

The "what's #1 right now" judgment lives in the policy's ordered lists (refresh
them from the live leaderboard). MODEL_SPECS is a dated fit table — update with
the policy. This script only enforces fit + records the choice; it hardcodes no
ranking.

Usage:
  resolve-current-sota.py --profile profiles/frontier.yaml \
      --policy /path/to/model-task-policy.yaml --out resolved.yaml --receipt receipt.json
"""
from __future__ import annotations
import argparse, json, sys
import yaml

# GPU VRAM (GB) by GKE accelerator label.
ACCEL_VRAM = {
    "nvidia-l4": 24, "nvidia-tesla-a100": 40, "nvidia-a100-80gb": 80,
    "nvidia-h100-80gb": 80, "nvidia-h200": 141, "nvidia-b200": 192,
}
BYTES_PER_PARAM = {"fp16": 2.0, "bf16": 2.0, "fp8": 1.0, "int8": 1.0,
                   "awq": 0.5, "gptq": 0.5, "int4": 0.5}
OVERHEAD = 1.2   # kv-cache + activations + runtime headroom

# Open providers (sovereign-servable). Closed = openai / anthropic / google.gemini etc.
OPEN_PROVIDERS = {"qwen", "meta_llama", "deepseek", "mistral", "baai",
                  "nomic", "mixedbread", "stability"}
def is_open(model_id: str) -> bool:
    prov = model_id.split(".", 1)[0]
    if prov in OPEN_PROVIDERS:
        return True
    return model_id.startswith("google.shieldgemma") or model_id.startswith("google.gemma")

# Dated fit table (June 2026; approximate params_b — refresh with the policy).
# hf = HuggingFace repo; params_b = total params (B); modality default text.
MODEL_SPECS = {
    "qwen.qwen3-235b-a22b":      {"hf": "Qwen/Qwen3-235B-A22B",        "params_b": 235},
    "qwen.qwen3-32b":            {"hf": "Qwen/Qwen3-32B",              "params_b": 32},
    "qwen.qwen3-vl":             {"hf": "Qwen/Qwen3-VL-32B-Instruct",  "params_b": 32, "modality": "vision"},
    "qwen.qwen3-reranker":       {"hf": "Qwen/Qwen3-Reranker-8B",      "params_b": 8},
    "qwen.qwen3-guard":          {"hf": "Qwen/Qwen3Guard-8B",          "params_b": 8},
    "qwen.qwen3-embedding":      {"hf": "Qwen/Qwen3-Embedding-8B",     "params_b": 8},
    "meta_llama.llama-4-maverick": {"hf": "meta-llama/Llama-4-Maverick", "params_b": 400},
    "meta_llama.llama-4-scout":  {"hf": "meta-llama/Llama-4-Scout",    "params_b": 109, "modality": "vision"},
    "meta_llama.llama-guard-4":  {"hf": "meta-llama/Llama-Guard-4-12B","params_b": 12},
    "deepseek.deepseek-r1":      {"hf": "deepseek-ai/DeepSeek-R1",     "params_b": 671},
    "deepseek.deepseek-r1-distill-llama-70b": {"hf": "deepseek-ai/DeepSeek-R1-Distill-Llama-70B", "params_b": 70},
    "qwen.qwq-32b":              {"hf": "Qwen/QwQ-32B",                "params_b": 32},
    "qwen.qwen2.5-vl-7b":        {"hf": "Qwen/Qwen2.5-VL-7B-Instruct", "params_b": 7, "modality": "vision"},
    "mistral.mistral-large-3":   {"hf": "mistralai/Mistral-Large-3",   "params_b": 123},
    "mistral.codestral":         {"hf": "mistralai/Codestral-22B",     "params_b": 22},
    "baai.bge-reranker-v2":      {"hf": "BAAI/bge-reranker-v2-m3",     "params_b": 0.6},
    "baai.bge-m3":               {"hf": "BAAI/bge-m3",                 "params_b": 0.6},
    "nomic.nomic-embed-text":    {"hf": "nomic-ai/nomic-embed-text-v1.5", "params_b": 0.14},
    "mixedbread.mxbai-rerank":   {"hf": "mixedbread-ai/mxbai-rerank-large-v2", "params_b": 0.5},
    "google.shieldgemma-2":      {"hf": "google/shieldgemma-2-2b",     "params_b": 2},
}


def required_gb(params_b: float, quant: str) -> float:
    return params_b * BYTES_PER_PARAM.get(quant, 2.0) * OVERHEAD


def resolve(profile: dict, policy: dict) -> tuple[dict, list]:
    fams = policy.get("model_families", {})
    accel = profile["iron"]["accelerator"]
    vram = ACCEL_VRAM.get(accel)
    if vram is None:
        sys.exit(f"unknown accelerator {accel}")
    receipt = []
    for m in profile["models"]:
        if not str(m.get("model", "")).startswith("RESOLVE"):
            continue  # already pinned
        fam = m.get("family")
        quant = m.get("quantization", "fp16")
        budget = m["gpus"] * vram * profile.get("defaults", {}).get("gpuMemoryUtilization", 0.92)
        prefs = [p for p in fams.get(fam, {}).get("preferred", []) if is_open(p)]
        chosen, considered = None, []
        for pid in prefs:
            spec = MODEL_SPECS.get(pid)
            if not spec:
                considered.append({"id": pid, "skip": "no spec"}); continue
            req = required_gb(spec["params_b"], quant)
            considered.append({"id": pid, "required_gb": round(req, 1), "fits": req <= budget})
            if req <= budget and chosen is None:
                chosen = {"policy_id": pid, "hf": spec["hf"], "params_b": spec["params_b"]}
        row = {"role": m["name"], "family": fam, "quant": quant,
               "budget_gb": round(budget, 1), "gpus": m["gpus"], "accelerator": accel,
               "considered": considered}
        if chosen:
            m["model"] = chosen["hf"]
            row["resolved"] = chosen
        else:
            m["model"] = "UNRESOLVED_no_open_model_fits_iron"
            row["resolved"] = None
            row["error"] = f"no open {fam} model fits {m['gpus']}×{accel} @ {quant} (budget {round(budget,1)}GB)"
        receipt.append(row)
    return profile, receipt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--out")
    ap.add_argument("--receipt")
    a = ap.parse_args()
    profile = yaml.safe_load(open(a.profile))
    policy = yaml.safe_load(open(a.policy))
    resolved, receipt = resolve(profile, policy)
    out = yaml.safe_dump(resolved, sort_keys=False)
    (open(a.out, "w").write(out) if a.out else sys.stdout.write(out))
    unresolved = [r["role"] for r in receipt if not r["resolved"]]
    print(f"\n# resolved {len(receipt)} roles; "
          f"{'ALL FIT' if not unresolved else 'UNRESOLVED: ' + ','.join(unresolved)}",
          file=sys.stderr)
    if a.receipt:
        json.dump({"profile": profile.get("profile"), "roles": receipt}, open(a.receipt, "w"), indent=2)
    sys.exit(1 if unresolved else 0)


if __name__ == "__main__":
    main()
