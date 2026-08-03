# KKO — KBpedia Knowledge Ontology (vendored into sophos-reasoner)

**File:** `kko-2.10.n3`
**SHA-256:** `d907919fb40f20ed39a7fde0e8d114027449d9354a1976ce8248db5634cb7b07`
**Bytes:** 327,797
**KKO ontology version:** v2.00 (`owl:versionIRI <http://kbpedia.org/kbpedia/v200>`)
**Namespace:** `http://kbpedia.org/ontologies/kko#`
**Retrieved:** 2026-07-28 · **Provenance verified against upstream:** 2026-07-29

## Source (sovereign, pinned)
- **`SocioProphet/kbpedia`** @ commit `3f888b397255b69d1439fd95823e97011ed9440b`
  (branch `master`), path `versions/2.10/kko-demo.n3`
  (raw: `https://raw.githubusercontent.com/SocioProphet/kbpedia/3f888b397255b69d1439fd95823e97011ed9440b/versions/2.10/kko-demo.n3`)
- Upstream of that fork: **`KBpedia/kbpedia`** (the org formerly known as Cognonto).

The engine's `PROVENANCE.md` cites `@ master`. A branch name is a MOVING reference, not a pin:
re-running it later can retrieve different bytes and still claim the same provenance. The commit
above is the pin (`master` has not moved since 2019-04-09, so the two resolve identically today —
which is exactly why the difference is invisible until it isn't).

## What it is
The **KKO upper ontology** — the Peircean-grounded typology that types the KBpedia Knowledge
Graph. This file carries the KKO TBox: **203 `owl:Class` declarations, 167 `rdfs:subClassOf`
axioms** (168 classes in the `kko:` namespace after parsing). It does NOT include the ~55k
reference-concept ABox — that is a separate artifact, vendored by hellgraph-service
(`apps/hellgraph-service/ontology/PROVENANCE.md`).

Vendored as **package data** (under `src/`, so it ships in the image the Dockerfile builds from
`COPY src`, and in any wheel/sdist via `[tool.setuptools.package-data]`). Loaded by
`reasoner.py::_kko_tbox()` so `reason(..., with_kko=True)` computes RDFS/OWL-RL closure over the
real KKO subClassOf hierarchy.

## Why a third copy, and not a reference to the engine's
The estate holds three byte-identical copies of this TBox: the HellGraph engine's
(`hellgraph ontology/kko/`), a checkout of it in `hellgraph-sprint`, and this one. Consuming the
engine's copy instead was considered and REJECTED on three concrete grounds:

1. **The engine does not ship it.** `@socioprophet/hellgraph`'s `package.json` publishes
   `files: ["ts/dist", "bin"]`. The `.n3` is not in the tarball at any version. The engine ships
   the ontology *pre-parsed* as `ts/src/kko-data.ts`, a TypeScript literal — not RDF.
2. **No runtime to read it with.** sophos-reasoner is `python:3.12-slim` + rdflib. Consuming the
   engine's copy means either adding Node to a Python image to evaluate a `.ts` module, or
   re-serialising a TS literal back into RDF — replacing a verified file with a lossy transform.
3. **Docker build contexts are per-app.** `apps/sophos-reasoner/Dockerfile` builds from
   `apps/sophos-reasoner`. A path into `apps/hellgraph-service` or into `node_modules` is not
   reachable from that context without widening it to the monorepo root.

So the copy stays — and the duplication is made SAFE rather than merely tolerated: every copy pins
the same `KKO_SHA256`, and this one asserts it at import. Duplication that is digest-bound is a
cache; duplication that is not is a fork waiting to happen.

## Where the digest is ENFORCED
`reasoner.py` computes the sha256 of these bytes **at import** (`verify_kko_integrity()`, the
`KKO_INTEGRITY` module constant) and raises `RuntimeError` when the file is present but its
digest is not the pinned one. Two failure modes, deliberately not alike:

| condition | behaviour | why |
|---|---|---|
| file **absent** | degrade — empty TBox, `with_kko` becomes a visible no-op via `kko_tbox_status().unavailable_reason` | a packaging condition, honestly reported; reasoning still serves |
| file **present, digest differs** | `RuntimeError` at import — the service does not start | a drifted ontology does not fail, it returns DIFFERENT ENTAILMENTS; there is no honest degraded mode for "wrong axioms" |

Proven by `tests/test_provenance.py`, which tampers with a *copy* of the package and asserts the
import actually dies (`test_tampered_kko_tbox_kills_import_in_a_real_process`) — not merely that
the recorded digest matches the file, which proves nothing about enforcement.

When the TBox is loaded, `kko_tbox_status()` returns `sha256` and `source` alongside the triple
count, so a caller can bind an entailment set to the exact ontology bytes that produced it.

## License / attribution
KBpedia and the KKO are released under **CC-BY-4.0**.
© Michael K. Bergman and Fred Giasson (Cognonto Corporation / KBpedia).
Attribution required; see <https://kbpedia.org> and <https://creativecommons.org/licenses/by/4.0/>.
This vendored copy preserves that attribution and does not modify the ontology content.

## Re-vendoring
1. Copy the new `.n3` from the pinned `SocioProphet/kbpedia` path over `data/kko-2.10.n3`.
2. `shasum -a 256 data/kko-2.10.n3` → update `KKO_SHA256` in `reasoner.py` **and** the header
   above **and** the engine's `ontology/kko/PROVENANCE.md`. The constant is shared across copies
   on purpose; moving one without the others is the drift this gate exists to catch.
3. Re-run the engine's `scripts/gen-kko.mjs` so `ts/src/kko-data.ts` matches the new source.
4. `PYTHONPATH=src pytest -q tests` — the integrity tests must pass on the new digest.
