# Lampstand integration staging area

This directory is the first-platform integration home for Lampstand inside `prophet-platform`.

## Classification
Lampstand is a **local daemon**, not a cluster microservice.

## Why
- indexes local files
- stores metadata and FTS content in local SQLite
- exposes a small daemon boundary
- integrates with platform storage env vars

## Layout
- `src/prophet_platform_lampstand/` - platform wrapper and receipt bridge
- `packaging/systemd/` - user-session service unit
- `UPSTREAM_IMPORT.md` - how to vendor/pin upstream Lampstand
- `docs/INTEGRATION.md` - integration notes

## Expected runtime modes
- dev/test: upstream unixjson fallback
- platform/prod: upstream TriTRPC transport once pinned and wired

## Out of scope in this phase
- Argo/K8s deployment manifests
- browser ingress
- pretending upstream Lampstand is already fully hardened
