# cloudshell-fog Go-Live Gate v0

This document defines the minimum promotion gate for `cloudshell-fog` inside `prophet-platform`.

## Purpose

The repository now contains:

- a deployable policy lane
- preferred runtime-v2 lanes
- standard and federal stack entrypoints
- inventory and decision-record contracts

That is necessary, but not sufficient, for production promotion.

The go-live gate exists to prevent operators from promoting an environment that is still using placeholders or missing explicit approval records.

## Gate command

Use:

```bash
./tools/validate-cloudshell-fog-go-live.sh standard
```

or

```bash
./tools/validate-cloudshell-fog-go-live.sh federal
```

## Requirements for passing

A profile-specific promotion can pass only when all of the following are true:

1. policy lane assets exist and validate
2. inventory assets exist and validate
3. bundle assets exist and validate
4. no tracked production placeholders remain in the known cloudshell-fog paths
5. a real profile-specific production decision record exists at:
   - `apps/cloudshell-fog/production-decision-record.standard.yaml`
   - or `apps/cloudshell-fog/production-decision-record.federal.yaml`
6. the chosen decision record contains no unresolved `REPLACE_WITH_...` tokens

## Operator workflow

### Standard lane

1. copy `production-decision-record.standard.example.yaml`
2. save as `production-decision-record.standard.yaml`
3. fill in real digest, secret-source profile, trust profile, approvers, and evidence refs
4. run `./tools/validate-cloudshell-fog-go-live.sh standard`
5. only then promote the standard stack

### Federal lane

1. copy `production-decision-record.federal.example.yaml`
2. save as `production-decision-record.federal.yaml`
3. fill in real digest, secret-source profile, trust profile, federal fallback region, approvers, and evidence refs
4. run `./tools/validate-cloudshell-fog-go-live.sh federal`
5. only then promote the federal stack

## Result

This turns the remaining unresolved production inputs into an explicit, reviewable gate rather than a hidden operator memory exercise.
