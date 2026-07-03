# Mesh tiers — one mesh per iron path, super-high-end available

The mesh is **iron-tiered**: each tier = a GPU class = a model class. Every tier
runs the **same mesh architecture** (base model + hellgraph KG grounding +
verify-repair + Noetica council); only the iron and the base model scale. The
base model is **never hardcoded** — a `resolve-current-sota` step picks the
current top open model that *fits the tier's iron* at run time (the fix for
recommending stale models from memory).

## Tiers

| Tier | Iron | Model class (resolved at run time) | vLLM | Substrate today | Product tier |
|------|------|-----------------------------------|------|-----------------|--------------|
| **edge** | 1–2× A100-40 (spot) / L4 | best **dense ≤~32B** open (e.g. Qwen3.x-class) | TP 1–2 | **GCP (current quota)** ✓ | free / dev |
| **pro** | 2× H100-80 | best **~280B-MoE / 13B-active** open (e.g. DeepSeek V4-Flash-class) | TP 2 (+INT4 opt) | GCP **after H100 quota** / GPU-cloud | paid |
| **frontier (super-high-end)** | **8× H100-80 (FP8)** or **8× H200** | current **#1 open frontier MoE** (DeepSeek V4-Pro 1.6T / Kimi K2.6 1T / GLM-5.1 744B) | TP 8 | **rented H100/H200 ephemeral** now; GCP/Azure/AWS after quota | premium / **prophet-mesh Enterprise** |

The thesis holds at every tier: **architecture (brain + jujitsu) closes the gap
to the frontier's published number** — the bigger the iron, the smaller the gap
the architecture has to close.

## Runtime model resolution (no more hardcoding)
`resolve-current-sota`: query the live open leaderboard (LiveCodeBench /
SWE-bench / coding-arena), filter to models that fit the tier's VRAM at the
tier's precision, pick #1, set `MESH_MODEL`. Serving manifests take `MESH_MODEL`
as a parameter — they never name a model.

## Super-high-end availability (the requirement)
Our GCP quota has **no H100/H200 / no A100-80GB** — so the frontier tier is not
servable on GCP today. Two paths to make it **available**, not theoretical:

1. **Ephemeral GPU-cloud rental (available now).** Rent 8× H100/H200 by the hour
   (Spheron / GMICloud / CoreWeave-class), serve via the same vLLM manifest +
   a remote kubeconfig, prove, tear down. ~$20–36/hr → ~$15–30 for a 45-min run.
   No GCP quota wait. This is how the frontier tier is available immediately.
2. **Cloud GPU quota (durable).** Request H100/H200 on GCP (and/or Azure/AWS via
   the `infra/tofu/environments/*` substrates — the multicloud work pays off
   here: field the frontier tier on whichever cloud has the iron).

Serving is **profile-driven**: `charts/mesh-serving` + `deploy/serving/profiles/`
`{edge,pro,frontier}.yaml`. Swap the profile to swap the iron + its matched
purpose→model map. `helm template mesh charts/mesh-serving -f profiles/frontier.yaml`
renders the 8-GPU TP=8 FP8 frontier deployment — the artifact that makes
super-high-end *available*, scheduling wherever 8× H100/H200 nodes exist.

## Ephemeral, always
Every tier spins up → proves → tears down. The frontier tier especially: 8× H100
bills only between apply and delete.

## Roster source of truth
The per-role model families come from `prophet-mesh/specs/model-task-policy.yaml`
(open_private + code/reasoning/document/image specialists + embeddings). Every
tier fields the **full open choir** (conductor · code · reasoning · document/vision
· embedding), sized to its iron — mirroring the local ollama choir (qwen2.5/coder,
deepseek-r1, llava, nomic-embed). `resolve-current-sota` picks the current #1 OPEN
model **within each family** that fits the tier. A code-exam parity run exercises
the conductor/code/reasoning subset; the profile still stands up the whole choir.
