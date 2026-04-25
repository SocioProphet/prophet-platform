# MesaNet Benchmark Candidate Plan

Status: draft benchmark candidate
Owner lane: platform evaluation fabric
Tracking issue: #154
Runtime posture: evaluate first; no production dependency yet.

## Purpose

MesaNet is a candidate sequence-modeling layer for the Prophet Platform evaluation fabric. We are treating it as a benchmark candidate, not as a replacement for search, durable memory, graph provenance, ontology storage, or platform evidence systems.

The inspected public implementation is in `fla-org/flash-linear-attention` at these paths:

- `fla/layers/mesa_net.py`
- `fla/ops/mesa_net/chunk.py`
- `fla/ops/mesa_net/chunk_cg_solver_fwd.py`
- `fla/models/mesa_net/modeling_mesa_net.py`
- `fla/models/mesa_net/configuration_mesa_net.py`

## Source inspection summary

`fla/layers/mesa_net.py` defines the `MesaNet` layer. It projects hidden states into query, key, value, decay, beta, and lambda paths. It applies short convolution over query and key streams. It keeps two recurrent state tensors, `h_kk` and `h_kv`. Training and prefill call `chunk_mesa_net`; cached decoding calls `mesa_net_decoding_one_step`.

`fla/ops/mesa_net/chunk.py` exposes the autograd wrapper and public chunk operation. It uses chunked execution, supports FlashAttention-style `cu_seqlens` for variable-length inputs, and can run query/key L2 normalization inside the kernel to reduce activation memory.

`fla/ops/mesa_net/chunk_cg_solver_fwd.py` implements the Triton forward conjugate-gradient solver. It solves for an optimized query-like vector before producing output. The kernel constrains head dimension and chunk geometry, so benchmark configs must record those values explicitly.

The model wrapper files provide Hugging Face-compatible `MesaNetModel` and `MesaNetForCausalLM` classes. They also allow hybrid insertion of standard attention layers at configured layer indexes.

## Candidate workload families

1. Retrieval trace replay: platform search-orchestrator traces, Sherlock search traces, and future Sherlock plus Lampstand integration traces.
2. Agent memory replay: memory-mesh recall-before-call and writeback-after-call traces, agent run capsules, and session replay samples.
3. Operational stream modeling: Global DevSecOps Intelligence operational-exhaust fusion samples, event envelopes, CI/CD traces, and runtime telemetry.
4. Alexandrian Academy learning traces: learning-search records, curriculum graph replay samples, and resource ranking traces.

## Baseline matrix

| Candidate | Role |
|---|---|
| Transformer attention | Control baseline for full attention behavior |
| MesaNet | Primary fixed-memory local-optimization candidate |
| DeltaNet or Gated DeltaNet | Linear/recurrent comparison point |
| Mamba2 | SSM comparison point |
| Hybrid MesaNet plus sparse/local attention | Long-range recall remediation candidate |

## Measurement contract

Each run should emit a platform evaluation record with candidate id, candidate version, implementation source, implementation commit, license, hardware profile, dtype, sequence length, batch size, chunk size, head dimension, training and decoding CG step counts, workload family, dataset id, trial count, metric facts, replay artifact references, observed failure modes, and supply-chain review status.

Primary metrics: task score, citation grounding precision, entity retention, event-order preservation, constraint retention, prefill latency, decode latency, tokens per second, peak memory, and CG iteration sensitivity.

## Adoption gates

MesaNet can advance only after reproducible eval-fabric evidence shows material value on SocioProphet-native workloads. It must not regress citation grounding, constraint retention, or sparse long-range recall without a hybrid remediation path. Any experiment must pin upstream commit and artifact hashes and avoid runtime network dependency fetches.

## Immediate plan

1. Add a candidate registry entry for `mesanet-fla`.
2. Add synthetic smoke workloads for retrieval, entity retention, log grouping, and agent replay.
3. Add a pinned no-network replay harness.
4. Emit metric facts and evidence receipts through the existing eval-fabric path.
5. Compare against Transformer, Mamba2, and Delta-family candidates.
6. Decide later whether adapters belong in memory-mesh, Sherlock search, or platform search-orchestrator.
