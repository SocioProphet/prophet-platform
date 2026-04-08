# Importing upstream Lampstand

This patch kit does not pretend to have fully vendored the upstream repo. Instead it gives the
platform a disciplined staging area and receipt bridge.

## Expected import target
Vendor or subtree upstream code under:

`apps/lampstand/vendor/lampstand-src/`

## Import steps
1. Pin an exact upstream commit from `SocioProphet/lampstand`.
2. Copy or subtree the following upstream roots:
   - `lampstand/`
   - `tests/`
   - `README.md`
   - `pyproject.toml`
   - `docs/SOCIOPROFIT_PLATFORM.md`
3. Preserve upstream licensing and provenance.
4. Keep all platform-specific glue in `src/prophet_platform_lampstand/`, not inside the vendored
   source tree.

## Why stage it this way
The platform should own packaging, receipts, policy boundary integration, and deployment shape
without turning the upstream service repo into a fork cemetery.
