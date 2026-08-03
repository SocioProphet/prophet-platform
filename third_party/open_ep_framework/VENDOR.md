# Vendored: open_ep_framework

Vendored copy of the estate's economic-profit / risk framework so prophet-platform services run the
**real** governed functions (single source of truth) rather than hand-mirrored formulas — we eat our
own dogfood.

- **Upstream:** SocioProphet/economic-prophet — package `open-ep-framework` (`src/open_ep_framework/`)
- **Commit:** `32281bcb1402946e00d3ff267579141b79e09817`
- **License:** Apache-2.0 — the upstream `LICENSE` is vendored verbatim alongside the source
  (`third_party/open_ep_framework/LICENSE`), as Apache-2.0 §4 requires for redistribution. Estate
  policy is MIT/Apache only; this satisfies it.
- **External dependencies:** none (stdlib only) — safe to vendor as source, no wheels/registry needed.
- **Consumed by:** `tools/emit_risk_ep_facts.py` → `apps/dashboard-bff` `/v1/risk/portfolio-facts`.

## Why vendored (not pip-installed)
The platform has no registry-install pattern for its own Python libs yet, and the package is
zero-dependency stdlib. Vendoring the source keeps CI hermetic and the dogfooding explicit.

## Refresh
Re-copy `src/open_ep_framework/` from economic-prophet `main`, refresh the vendored `LICENSE` from
the upstream repo root, and bump the commit SHA above:
```
cp -r <economic-prophet>/src/open_ep_framework third_party/open_ep_framework
cp    <economic-prophet>/LICENSE               third_party/open_ep_framework/LICENSE
```
A drift test (`tests/platform_stubs/test_risk_ep_facts.py`) asserts the producer's numbers equal the
vendored functions called directly, so silent divergence fails CI.
