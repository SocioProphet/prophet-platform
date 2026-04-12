# Time-Series ML Plane in Prophet Platform

This document records how the current time-series / MLOps work fits into `prophet-platform`.

## Position in the platform

The time-series lane is a **platform subsystem**, not an app concern.

It sits on top of:
- platform durability primitives (commit log + immutable lake)
- platform contracts and schemas
- local and cluster deployment wiring

It serves:
- training
- evaluation / gating
- promotion
- serving
- reproducible developer workflows

## Supported model-family doctrine

Prophet Platform should support a portfolio of time-series model families rather than a single stack.

### Baselines and classical models
- naive / seasonal naive
- lagged linear baselines
- ARIMA / SARIMA
- ETS / exponential smoothing
- state-space / Kalman-style models
- VAR / VECM where appropriate

### Volatility / finance-native models
- ARCH / GARCH
- EGARCH
- GJR-GARCH / TGARCH
- heavy-tailed volatility models
- HAR-RV and related realized-volatility baselines

### ML + deep models
- lag-feature gradient boosting
- recurrent nets (LSTM / GRU)
- seq2seq models
- temporal CNN / TCN
- transformer-style time-series models
- global / multi-series models

### Structured finance objects
- implied-volatility surface models
- term-structure / curve models
- constraint-aware structured objects

## Platform contract

The platform should stay **task-first** and **contract-first**.

The relevant contracts are:
- forecast model contract
- risk model contract
- simulator / generator contract
- registry / provenance contract
- workflow / promotion-gate contract

The platform does not hard-code Ray, KServe, or any single engine as the only valid runtime.
It should preserve pluggability while keeping provenance and promotion semantics stable.

## Minimal execution truth

Before expanding the family roster indefinitely, we must keep one executable local thin slice working:

- one real trainer
- one real control plane
- one real gateway
- one real model spec
- one real smoke test

That thin slice is the closure path we preserve while the model-family surface expands.

## Relationship to CLI

`prophet-cli` should expose a façade over this lane:
- `prophet dev up`
- `prophet train run`
- `prophet model register`
- `prophet model promote`
- `prophet infer`
- `prophet dev destroy`

The CLI is a façade. `prophet-platform` is the runtime home.
