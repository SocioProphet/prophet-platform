# Zero-trust kernel schemas (vendored)

**Source repo:** `SocioProphet/mcp-a2a-zero-trust` (public, GitHub)
**Pinned commit:** `0399e8ae84f0be8194ce57e56b14ba4bbb807f47` — 2026-05-21,
_"Bind MCP/A2A interop to Operation Plane trust boundaries"_
**Vendored:** 2026-07-18 (prophet-platform `07aeabdc`, PR #853; extended by `298d3aa2`, PR #858)
**Provenance established and byte-verified:** 2026-07-29

## What these are
The estate's own control-zone authority kernel — **not** the public `mcp` SDK. The compute-gateway
registers as a governed PROVIDER inside that kernel and emits kernel-shaped evidence
(`capability_registry()`, `grant_check()`, `attestation_bundle()` in `zerotrust.py`). These six
documents are the contract that evidence is validated against, at runtime and in tests.

## The six files, with upstream paths and digests

| vendored file | upstream path @ `0399e8ae` | sha256 | bytes |
|---|---|---|---|
| `capability_registry.schema.json` | `mcp/registry/capability_registry.schema.json` | `f3e793394baee2c4782762de565e988b4fc527639b41839aa859d2f9cbb3d73d` | 3,263 |
| `attestation_bundle.schema.json` | `schemas/canonical/attestation_bundle.schema.json` | `485d0ed689cc1b3184a18d555bb3eba75c4110f7087d0c3c6c54c575447a4272` | 1,434 |
| `grant.schema.json` | `schemas/canonical/grant.schema.json` | `2aac20b5fc9ce2ef72c0609bc1687f2b4b17a2167ef3148fa8ad3c4c1494f0b1` | 2,991 |
| `policy_decision.schema.json` | `schemas/canonical/policy_decision.schema.json` | `fa836113aeda2b1d65b9a3868cb692e266fa51d516bb3a3f248e58e74d6dfc89` | 2,027 |
| `quorum_proof.schema.json` | `schemas/canonical/quorum_proof.schema.json` | `d3ceec20d3268c30c1f0fda17f0981654a850ad39073ac5b1ff4aff62a0b2bb2` | 1,240 |
| `tool_grant_check.schema.json` | `schemas/interop/tool_grant_check.schema.json` | `360c5c98c43742aa7f930a472fd8662eff28bba32eca9b20dd8e76d3077c923c` | 3,282 |

Note the **flattening**: upstream separates `mcp/registry/`, `schemas/canonical/` and
`schemas/interop/`; the vendored copies sit in one directory. Only the location changed — the
bytes are identical, which is what the digests above prove. The upstream path column is what makes
a re-vendor mechanical rather than a search, and is exactly what was missing when these six were
described only as "vendored".

### Verification performed 2026-07-29
Each file fetched from `raw.githubusercontent.com` at the pinned commit and compared with `cmp`:
**all six byte-identical.** Repeated against the kernel's `main`
(`93c4b831ca2394990b5302d0acea03f40d07537e`): **also byte-identical** — the pin is not merely
recorded, it is still current, so this vendoring carries no freshness debt today.

## Licence
`SocioProphet/mcp-a2a-zero-trust` is a **first-party SocioProphet repository**, so no third-party
licence obligation attaches to these files.

**Stated honestly:** the repo declares **no explicit licence** — there is no `LICENSE` file at the
pinned commit, and GitHub reports no detected licence for it. That is recorded here as an observed
fact, not resolved by assumption. It is a gap on the *kernel* repo's side (an unlicensed public
repo is "all rights reserved" by default, which is probably not the intent for an estate contract
others are meant to conform to) and is raised in this PR's body for the owning lane rather than
guessed at here.

## Where the digests are ENFORCED
`zerotrust.py` verifies this table **at import** — `verify_vendored_schemas()`, whose result is the
`SCHEMA_DIGESTS` module constant. Three refusals, all `RuntimeError`, all fatal at boot:

| condition | why it is fatal |
|---|---|
| a pinned schema is **missing** | validation would otherwise raise deep inside a request instead of at boot |
| a pinned schema **drifted** | these documents decide what a ToolGrantCheck and an AttestationBundle *are*; a loosened `required` or a widened enum silently admits evidence the kernel would reject |
| an **unpinned** `*.schema.json` appears here | `_registry()` globs this directory and registers every document by `$id`, so an unvendored file can satisfy a canonical `$ref` and quietly become the contract — vendoring is a closed set or it is not vendoring |

Proven by `tests/test_schema_provenance.py`, which tampers with a copy of the package and asserts a
real interpreter refuses to import it — separately for the drifted, missing and unpinned cases.

## Re-vendoring
1. Pick the new kernel commit; update `KERNEL_COMMIT` in `zerotrust.py` and the header above.
2. For each row: copy the file from its upstream path, then
   `shasum -a 256 <file>` → update `SCHEMA_PROVENANCE` in `zerotrust.py` **and** the table above.
3. Adding or dropping a schema means editing `SCHEMA_PROVENANCE` — the file set is pinned too, so
   a new schema cannot be dropped in without provenance.
4. `PYTHONPATH=src pytest -q tests` — the provenance tests must pass on the new digests.
