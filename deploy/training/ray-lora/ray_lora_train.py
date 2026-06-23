"""ray_lora_train — LoRA fine-tune of a base model on VERIFIED production traces, on Ray Train.

This is the execution muscle behind RAY_RUNTIME_REF (runtime-asset:prophet-ray-ml, role ray-train):
the platform declared Ray as the training standard everywhere but never actually ran a fine-tune.
This does — wrapping the existing peft LoRA logic in ray.train.torch.TorchTrainer so it scales on
the cluster and reports through Ray, then writes a LoRA adapter (optionally to GCS) for the
promotion gate + serving step to pick up.

Input: an SFT JSONL of rejection-sampled VERIFIED traces (each line one example). Accepted shapes:
    {"text": "..."}                      # pre-formatted
    {"input": "...", "output": "..."}    # noetica verified Trace
    {"prompt": "...", "completion": "..."}
Output: a PEFT LoRA adapter at ADAPTER_OUT (and uploaded to ADAPTER_GCS if set).

Config via env (all optional except SFT_PATH):
    BASE_MODEL      default Qwen/Qwen2.5-Coder-7B-Instruct  (set tiny-gpt2 for a CPU smoke test)
    SFT_PATH        path to the verified SFT JSONL          (required)
    ADAPTER_OUT     local adapter dir   (default /tmp/adapter)
    ADAPTER_GCS     gs://... to upload the adapter          (optional)
    LORA_R / LORA_ALPHA / EPOCHS / BATCH_SIZE / LR / MAX_LEN
    RAY_NUM_WORKERS default 1            RAY_USE_GPU default 1 (set 0 for CPU smoke test)

Run (cluster): submitted by the RayJob (lora-rayjob.yaml).
Run (local CPU smoke, $0):
    BASE_MODEL=sshleifer/tiny-gpt2 RAY_USE_GPU=0 SFT_PATH=sample.sft.jsonl EPOCHS=1 \
        python ray_lora_train.py
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any


# ── pure data path (no ray/torch — unit-testable at $0) ────────────────────────────────────────

def read_sft_texts(path: str) -> list[str]:
    """Parse the verified-trace JSONL into flat training texts. Tolerant of the three input shapes;
    skips blank lines and rows with no usable content."""
    texts: list[str] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            text = row.get("text")
            if not text:
                left = row.get("input") or row.get("prompt") or ""
                right = row.get("output") or row.get("completion") or ""
                text = f"{left}\n{right}".strip()
            if text:
                texts.append(text)
    return texts


def _cfg() -> dict[str, Any]:
    return {
        "base_model": os.getenv("BASE_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct"),
        "sft_path": os.environ["SFT_PATH"],
        "out_dir": os.getenv("ADAPTER_OUT", "/tmp/adapter"),
        "r": int(os.getenv("LORA_R", "16")),
        "alpha": int(os.getenv("LORA_ALPHA", "32")),
        "epochs": float(os.getenv("EPOCHS", "3")),
        "bs": int(os.getenv("BATCH_SIZE", "4")),
        "lr": float(os.getenv("LR", "2e-4")),
        "max_len": int(os.getenv("MAX_LEN", "1024")),
    }


# ── the per-worker training function (runs under Ray Train) ─────────────────────────────────────

def train_func(config: dict[str, Any]) -> None:
    import torch  # noqa: F401  (ensures CUDA visibility is logged)
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    tok = AutoTokenizer.from_pretrained(config["base_model"])
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    model = AutoModelForCausalLM.from_pretrained(config["base_model"])
    model = get_peft_model(
        model,
        LoraConfig(r=config["r"], lora_alpha=config["alpha"], lora_dropout=0.05, task_type="CAUSAL_LM"),
    )
    model.print_trainable_parameters()

    texts = read_sft_texts(config["sft_path"])
    if not texts:
        raise SystemExit(f"no usable training examples in {config['sft_path']}")
    ds = Dataset.from_dict({"text": texts}).map(
        lambda b: tok(b["text"], truncation=True, padding="max_length", max_length=config["max_len"]),
        batched=True,
        remove_columns=["text"],
    )

    args = TrainingArguments(
        output_dir=config["out_dir"],
        per_device_train_batch_size=config["bs"],
        num_train_epochs=config["epochs"],
        learning_rate=config["lr"],
        logging_steps=5,
        save_strategy="no",
        report_to=[],
        # Use the GPU only when real CUDA is present (the Ray GPU worker). Off-GPU runs (CPU cluster
        # or Mac dev, where torch would otherwise grab MPS and mis-place tensors) are pinned to CPU.
        use_cpu=not torch.cuda.is_available(),
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=ds,
        data_collator=DataCollatorForLanguageModeling(tok, mlm=False),
    )

    # Canonical Ray<>HF integration when available — report metrics + checkpoints through Ray Train.
    try:
        from ray.train.huggingface.transformers import RayTrainReportCallback, prepare_trainer

        trainer.add_callback(RayTrainReportCallback())
        trainer = prepare_trainer(trainer)
    except Exception:  # local/CPU smoke runs without ray.train installed still train fine
        pass

    trainer.train()

    # Save the adapter on rank 0 only (single-worker LoRA: always rank 0).
    rank0 = True
    try:
        from ray.train import get_context

        rank0 = get_context().get_world_rank() == 0
    except Exception:
        pass
    if rank0:
        model.save_pretrained(config["out_dir"])
        tok.save_pretrained(config["out_dir"])
        print(f"LoRA adapter saved to {config['out_dir']}", flush=True)
        gcs = os.getenv("ADAPTER_GCS", "").strip()
        if gcs:
            subprocess.check_call(["gsutil", "-m", "cp", "-r", f"{config['out_dir']}/.", gcs])
            print(f"adapter uploaded to {gcs}", flush=True)


def main() -> None:
    config = _cfg()
    use_gpu = os.getenv("RAY_USE_GPU", "1") == "1"
    num_workers = int(os.getenv("RAY_NUM_WORKERS", "1"))

    from ray.train import RunConfig, ScalingConfig
    from ray.train.torch import TorchTrainer

    trainer = TorchTrainer(
        train_func,
        train_loop_config=config,
        scaling_config=ScalingConfig(num_workers=num_workers, use_gpu=use_gpu),
        run_config=RunConfig(name="lora-verified-traces"),
    )
    result = trainer.fit()
    print(f"RAY LORA DONE — base={config['base_model']} adapter={config['out_dir']} metrics={result.metrics}", flush=True)


if __name__ == "__main__":
    main()
