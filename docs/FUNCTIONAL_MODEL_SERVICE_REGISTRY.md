# Functional Model Service Registry

## Purpose

The functional model service registry records platform-facing service surfaces for SocioProphet functional AI capabilities.

This registry is not a model zoo and does not store model binaries. It records governed service identity, source repositories, evidence expectations, promotion state, and SourceOS carry policy.

## Ownership split

- `SocioProphet/functional-model-surfaces` owns normative standards.
- `SocioProphet/prophet-platform` owns platform service records and runtime registration seams.
- `SociOS-Linux/*lab` repositories own local lab execution and candidate artifacts.
- `SourceOS-Linux/sourceos-model-carry` owns client-side carry references and local evidence output.

## Initial services

The initial registry includes platform records for:

- Holmes language intelligence fabric
- SourceOS AI carry
- speech
- OCR
- image
- video
- translation
- embedding / retrieval
- model router
- guardrail fabric
- agent registry

## SourceOS carry rule

SourceOS may carry clients, launch profiles, signed service references, cache policy, and evidence collectors.

SourceOS must not carry mutable model lifecycle authority. Any service registry record that grants SourceOS artifact replacement or model promotion authority must fail validation.

## Promotion rule

A service is not stable unless it has evidence requirements and a promotion state. The first registry pass may mark services as `bootstrap` or `experimental`, but records must still declare evidence requirements and ownership boundaries.
