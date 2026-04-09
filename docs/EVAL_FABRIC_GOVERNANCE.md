# Eval Fabric Governance Notes

This document explains the platform-governance objects added under `schemas/eval/`.

## Purpose

The eval fabric should not only store scores. It should also store:
- how a score was reproduced
- how a score moved over time
- what source methodology snapshot was used
- how external metric names map into the platform canonical metric vocabulary

## Core governance objects

### ReproLedgerEntry

Pins the reproducibility state of a run:
- prompt pack
- fixture snapshot
- tool bundle
- seed policy
- environment hash
- methodology snapshot hash
- replay artifact reference

### CausalAttribution

Explains score movement by decomposition across:
- model delta
- scaffold delta
- ontology delta
- retrieval delta
- benchmark drift
- judge drift

### MethodologySnapshot

Hashes and timestamps the evaluation methodology or external-source methodology state used when facts were ingested or scored.

### MetricCrosswalk

Maps external or source-specific metric names into the platform canonical metric registry.

## Why this matters

Without these objects, the dashboard can look precise while actually hiding:
- evaluator drift
- benchmark drift
- source-methodology mismatch
- score movement with no attributable cause

## Next platform step

These schema objects should next be:
1. seeded with example records
2. surfaced in replay/provenance API responses
3. linked from score computation and competition-intelligence ingest
