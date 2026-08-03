# Prophet Understand Repo-Backed Vertical Slice

## Purpose

This document defines the first real repo-backed Prophet Understand / Repo Intelligence vertical slice across the estate.

The fixture-backed slice proves the platform contract locally. The repo-backed slice proves that the sibling repos can cooperate:

```text
Prophet Understand emitter emits artifact
-> Prophet Platform validates artifact
-> Lampstand indexes artifact
-> Sherlock searches index
-> Policy Fabric evaluates artifact
-> Delivery Excellence scores artifact
```

> Provenance note: the repo-intelligence emitter (`tools/emit_prophet_understanding.py`) is
> prophet-platform-owned and stdlib-only. It was severed from the third-party-derived
> `smart-tree` tool; the pipeline no longer depends on a `smart-tree` checkout or its `st`
> binary. See `docs/adr` / the sever changelog for history.

## Script

Run from `SocioProphet/prophet-platform`:

```bash
python3 tools/run_prophet_understand_repo_backed_slice.py \
  --dev-root "$HOME/dev" \
  --target-repo prophet-platform \
  --target-full-name SocioProphet/prophet-platform \
  --query "what depends on this contract?"
```

`--target-repo` may be any repo under `--dev-root` you want to scan.

## Required sibling repos

The script expects these directories under `--dev-root`:

- `prophet-platform`
- `lampstand`
- `sherlock-search`
- `policy-fabric`
- `delivery-excellence`

## Required scripts

The repo-backed slice calls:

- `prophet-platform/tools/emit_prophet_understanding.py`
- `prophet-platform/tools/validate_prophet_understand.py`
- `lampstand/tools/index_prophet_understanding.py`
- `sherlock-search/tools/search_prophet_understanding.py`
- `policy-fabric/tools/evaluate_prophet_understand_policy.py`
- `delivery-excellence/tools/score_prophet_understand.py`

## Outputs

By default, the script writes:

```text
prophet-platform/build/prophet-understand/repo-backed/lampstand-index.json
prophet-platform/build/prophet-understand/repo-backed/sherlock-search.json
prophet-platform/build/prophet-understand/repo-backed/policy-decision.json
prophet-platform/build/prophet-understand/repo-backed/delivery-scorecard.json
prophet-platform/build/prophet-understand/repo-backed/repo-backed-summary.json
prophet-platform/build/prophet-understand/repo-backed/logs/*.log
```

The emitted graph artifact is written into the scanned repo:

```text
<target-repo>/.prophet/prophet-understanding.json
```

## Pass condition

The slice passes when:

- The emitter writes `.prophet/prophet-understanding.json`.
- Prophet Platform validates the emitted artifact against the v0 contract.
- Lampstand creates deterministic index records.
- Sherlock returns at least a valid query response object.
- Policy Fabric returns a machine-readable policy decision.
- Delivery Excellence returns a scorecard.
- The summary status is `passed`.

## Non-goals

- This script does not install hooks.
- This script does not mutate source files except writing the generated graph artifact under `.prophet/` in the target repo and build outputs under `prophet-platform/build/`.
- This script does not grant autonomous execution authority.
- This script does not replace repo-specific CI.

## Next integration steps

After the slice passes:

1. Commit a reviewed fixture or generated artifact only where useful.
2. Promote the Lampstand/Sherlock/Policy/Delivery helpers into package-level commands.
3. Render the produced artifact in the SocioProphet `/repo-map` workbench.
4. Add branch-protection-aware PR impact reports for graph-affecting changes.
