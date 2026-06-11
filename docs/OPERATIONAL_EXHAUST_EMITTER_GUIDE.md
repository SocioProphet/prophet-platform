# Operational Exhaust Emitter Guide

## Purpose

This document defines the first runtime-side emission guidance aligned to the
`global-devsecops-intelligence` operational exhaust fusion profile.

It is the source-side counterpart to the ops-domain fusion boundary and machine-readable
profile in `SocioProphet/global-devsecops-intelligence`.

## Scope

This guide applies to platform services, market-data runtimes, and trader-agent runtimes
that need to emit normalized operational exhaust without relocating canonical domain
semantics out of their owning repositories.

## Required event families

Runtime surfaces SHOULD emit at least the following normalized event families:
- `OperationalExhaustObserved.v0.1`
- `TraderAgentExecutionObserved.v0.1` when the runtime performs or supervises trading actions

## Emission rules

1. Emit a normalized operational event whenever a runtime crosses an operational boundary:
   - health degraded/restored
   - queue pressure / backpressure changes
   - policy/evidence receipt emitted
   - market-data gap detected
   - replay started/completed
   - trader-agent strategy run started/stopped
   - order intent created / execution acknowledged / filled / rejected / cancelled
   - risk control or kill-switch activation

2. Preserve canonical domain payloads in their owning stores. Emit references, hashes,
   and receipts here rather than copying raw sensitive payloads.

3. Populate common required fields consistently:
   - `event_id`
   - `observed_at`
   - `source_repo`
   - `source_surface`
   - `source_runtime`
   - `environment_ref`
   - `trace_ref`
   - `projection_family`

4. Trader-agent runtimes SHOULD also populate:
   - `strategy_run_ref`
   - `model_ref`
   - `feature_snapshot_ref`
   - `market_window_ref`
   - `risk_policy_ref`
   - `order_intent_ref`
   - `execution_ref`
   - `venue_ref`

## Export destination

These normalized operational events are intended to be projected into
`SocioProphet/global-devsecops-intelligence`, which owns the ops-domain fusion layer,
measurement plane, and derived operational graph projections.

## Deliberate non-goals

- This guide does not redefine canonical market semantics.
- This guide does not replace canonical wire/storage invariants.
- This guide does not require that every runtime store all exhaust locally.
  Emission may be direct, buffered, or receipt-based depending on runtime shape.

## Immediate follow-on

- add concrete emitter helpers in the runtime services that now own market-data and trader execution lanes
- add extraction/mapping rules in `global-devsecops-intelligence`
- add replay / post-trade evaluation emission guidance for trader-agent learning loops
