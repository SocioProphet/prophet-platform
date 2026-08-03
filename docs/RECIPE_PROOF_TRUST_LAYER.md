# RecipeProof — the CK/CM PROOF + TRUST layer

**What it is.** The keystone that turns a *runnable recipe* into a **portable,
reproducible, citable PROOF with a trust attestation**. MLCommons Collective
Knowledge (CK/CM) makes recipes portable; this layer goes one step further and
binds a recipe *execution* to a verifiable proof a third party can check without
trusting us. This is the Collective-Knowledge parity/**beat** — not just MLPerf.

**Consume, don't fork.** This layer adds a thin binding on top of pieces that
already exist in the estate:

| Piece | Source | Role in a RecipeProof |
|---|---|---|
| reproduce path + tolerance gate | `tools/reproduce_bench.py` (#1269) | runs the recorded run, emits the receipt + repro-ledger |
| repro-ledger contract | `schemas/eval/repro-ledger-entry.schema.json` | the ledger entry (not forked) |
| receipt spine | reproduce_bench spine records (SHA-256 hash-chained) | the tamper-evident `receipt_ref` |
| division rules + validity | `tools/validate_submission.py` + `schemas/eval/division-rules.json` (#1271) | the open/closed `division` verdict + trust gates |
| DataCite concept/version client | `apps/lattice-studio/.../datacite.py` (#1267) | the optional citable `doi_ref` |
| recipe register | crystal-atlas `internal-models` register (**#1287, OPEN**) | the `recipe_ref` target |

## The contract

`schemas/eval/recipe-proof.schema.json` — a `RecipeProof` binds:

- `recipe_ref` — a **soft** reference to a crystal-atlas recipe (`recipe_id`
  matching the register's `^internal-model:[a-z0-9-]+$` id contract, plus an
  optional SHA-256 `content_digest`).
- `run_id` / `bench`, `repro_ledger_ref`, and `receipt_ref` (the SHA-256
  `entry_digest` of the hash-chained spine record).
- `headline` — `metric_id`, reproduced `value`, `epsilon`, `determinism_class`.
- `division` — `OPEN` / `CLOSED`.
- `submission` — the descriptor `validate_submission` scores (the division gates
  run over *this*, nothing is re-implemented).
- `trust_attestation` — `clean_eval` + `provider_neutrality` + `no_laundering`,
  **always** required and **proven** (not trusted) at verify time.
- optional `doi_ref` — concept + version DOI.

## The two verbs (`tools/recipe_proof.py`)

```
# ASSEMBLE: run the recipe via reproduce_bench, emit receipt + ledger, bind a proof
make recipe-proof BENCH=isota RUN=opus-class-r1 \
  RECIPE=internal-model:isota-tournament DIVISION=CLOSED \
  SUBMISSION=schemas/eval/examples/recipe-proof/submission.closed.example.json \
  OUT=build/recipe-proof/rp.json

# VERIFY (fail-closed, independent): chain intact + metric within epsilon +
# division gates pass + trust gates proven + recipe_ref resolvable
make recipe-proof-verify PROOF=schemas/eval/examples/recipe-proof/recipe-proof.example.json
```

## Teeth (both ways — `make validate-recipe-proof`, CI `recipe-proof-gate`)

A RecipeProof **VERIFIES** with a valid recipe_ref, an intact receipt chain, the
headline within ε, and passing division/clean-eval/provider-neutrality gates.

**REJECTED** (fail-closed): a tampered/missing receipt (broken chain), metric
drift beyond ε, a failed division gate (e.g. no clean-eval cert), an unresolvable
recipe_ref (id absent from the register), a recipe_ref content-digest mismatch, a
CLOSED proof missing a required field, and a lying trust attestation.

## Coordination with crystal-atlas #1287 (no collision)

The recipe **register** is built in a parallel effort (#1287, OPEN). This layer
does **not** reimplement or fork it — it *references* a recipe by id.

- **No register on main yet** → `recipe_ref` resolution is **deferred**
  (`pending_register`): the reference is format-checked but not bound, and a proof
  still verifies on every other gate.
- **A register supplied** (`--register`) → resolution is **hard**: an id absent
  from the register, or a `content_digest` that does not match the register
  entry's content address, is **REJECTED**.

When #1287 lands, wire the verify/CI step to
`contracts/crystal-atlas/registry/internal-models.v0.json` (identical id
contract) and the binding activates with zero schema changes. The test fixture
`tests/platform_stubs/fixtures/crystal-atlas-register.fixture.json` stands in for
the register until then.

> SHA-256 is the FIPS 180-4 *algorithm* (via stdlib `hashlib`), **not** a FIPS
> 140-validated cryptographic module.
