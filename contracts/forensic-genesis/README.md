# Forensic Genesis Runtime Contract Stub

This directory is the runtime-facing landing zone for the Forensic Genesis edge lane.

## Purpose
The normative schemas and compatibility rules live in `SocioProphet/prophet-platform-standards`. This directory exists so runtime services have an obvious home for:
- generated bindings derived from the standards repo
- topic consumer adapters
- local validation fixtures used by runtime code
- import notes tying runtime code to pinned standards revisions

## First-pass event family
- SNMP observations
- Mount observations
- Verification completion
- Seal completion

## Rules
- Do not redefine canonical value schemas here.
- Prefer generated bindings or copies derived from pinned standards imports.
- Keep runtime consumers transport-aware but standards-neutral.
