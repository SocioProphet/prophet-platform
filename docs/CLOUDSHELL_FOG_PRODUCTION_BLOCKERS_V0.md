# cloudshell-fog Production Blockers v0

This document records the current known blockers to promoting `cloudshell-fog` as a real production deployment through `prophet-platform`.

## Current blocker set

### 1. No authoritative published gateway digest in-repo

The platform repo still uses placeholders for the runtime image digest in deployment examples and decision records.

Status: open

### 2. No selected secret-source implementation

The repo now documents supported secret-source patterns, but no environment-owned choice has been committed as the production truth.

Status: open

### 3. No selected signature-trust implementation

The platform repo now documents key-backed vs keyless options, but the vendored verification policy still carries placeholder trust material.

Status: open

### 4. Federal fallback region unresolved

The federal lane requires a real fallback region choice, but this remains a placeholder and must be supplied by the environment owner.

Status: open

### 5. Older runtime overlays still exist

The older non-v2 overlays are now explicitly transitional, but they still exist in-repo and can create operator confusion until retired from active use.

Status: open

## What is not blocked anymore

The following are now present in the repo:

- policy lane and Argo application
- runtime-v2 standard and federal lanes
- standard and federal stack entrypoints
- deployment inventory contract
- production decision-record contract
- go-live validator
- Fog Stack Access binding and compatibility scaffold

## Exit criteria

All blockers above must be closed before calling the deployment production-ready.
