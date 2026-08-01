# Workspace Control Plane — Phase 4 (rails + attention registry)

Implements **Phase 4**: mirror/live/action rail orchestration (D4) and the
attention registry (D5), on the Phase-1 object model and Phase-3 connectors.

## Rail orchestration (`tools/rail_orchestrator.py`, D4)

`orchestrate(roots, connectors)` runs one pass, routing each root by its
`sync_mode`:

| Rail | Behavior |
|---|---|
| mirror | connector produces indexed `asset.v0` + `event.v0`; cursor advances |
| live | events only, no cached asset; cursor advances |
| action | no ingestion — deferred to `workflow-run` (side-effect rail) |

`apply_cursors` persists advanced delta cursors back onto the roots. The
orchestrator never fetches anything itself; it drives the Phase-3 connectors, so
the split stays structural rather than one uncontrolled path.

## Attention registry (`tools/attention_registry.py`, D5)

Keeps half-processed work discoverable before deep indexing. `should_surface`
and `AttentionRegistry` operate over `attention-mark.v0`:

| Mode | Surfaces when |
|---|---|
| pin | always |
| watch | one of its event triggers fires |
| revisit | a scheduled `at:<iso>` trigger is due, or on an event |
| incubate | its decay half-life has elapsed, or on a trigger |
| hold | never (until released to another mode) |
| forget | never (tombstoned) |

**Suppression wins:** if any of a mark's suppression rules is active, it does not
surface regardless of mode. `resolve_surfacing` returns due marks in stable order;
`add`/`release`/`forget` manage lifecycle.

## Validation

`tools/tests/test_rails_attention.py` — 10 tests: rails honored, cursors advance,
missing-connector raises, mark schema conformance, each mode, suppression, and
registry transitions. Path-filtered CI: `.github/workflows/control-plane-rails.yml`.

## Next (Phase 5)

Trust broker + signed catalog verification (TUF/Sigstore) over the
`capability-manifest`/`topic-manifest`/`catalog-entry` schemas already frozen.
