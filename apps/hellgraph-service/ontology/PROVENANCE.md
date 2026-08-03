# KBpedia Reference Concepts — the RC ABox (vendored)

**File:** `kbpedia-rc-2.10.n3.gz`
**SHA-256 (as vendored, gzipped):** `e48d0ff7708d647cb35b1bcbcca05a041c731e5a1bfcea296209a086b72da06a`
**Bytes (gzipped):** 8,954,726
**SHA-256 (inflated N3):** `0c23ca83ac0e1270c4ea5335268b54a32577ba5d8cec0e33345f48e2ac60e95f`
**Bytes (inflated):** 37,618,857
**KBpedia version:** 2.10 · **Namespace:** `http://kbpedia.org/kko/rc/`
**Vendored:** 2026-07-28 (commit `7aa06ab5`) · **Provenance verified against upstream:** 2026-07-29

## Source (sovereign, pinned)
- **`SocioProphet/kbpedia`** @ commit `3f888b397255b69d1439fd95823e97011ed9440b` (branch `master`)
- Path: `versions/2.10/kbpedia_reference_concepts.zip` (8,982,294 bytes,
  sha256 `59ae9070b34946c7acea121604b291d82d0ebf47232fc0ee4615028e1e4d56ce`)
- The zip holds exactly one entry: `kbpedia_reference_concepts.n3`, 37,618,857 bytes.
- Upstream of that fork: **`KBpedia/kbpedia`** (the org formerly known as Cognonto).

**Transformation applied:** unzip, then re-gzip. The RDF is **unmodified** — the inflated bytes
are byte-identical to upstream's, which is what the second digest above proves. Only the
compression container changed (zip → gzip), so the image needs no unzip tooling and `server.ts`
can inflate with Node's built-in `zlib`.

### Verification performed 2026-07-29
```
$ curl -sfL https://raw.githubusercontent.com/SocioProphet/kbpedia/3f888b39.../versions/2.10/kbpedia_reference_concepts.zip -o rc.zip
$ unzip -p rc.zip kbpedia_reference_concepts.n3 | shasum -a 256
0c23ca83ac0e1270c4ea5335268b54a32577ba5d8cec0e33345f48e2ac60e95f
$ gunzip -c ontology/kbpedia-rc-2.10.n3.gz | shasum -a 256
0c23ca83ac0e1270c4ea5335268b54a32577ba5d8cec0e33345f48e2ac60e95f   # identical
```

## What it is, and why drift here is dangerous
The **KBpedia reference-concept ABox**: ~55,124 reference concepts (RCs) with ~75k
`rdfs:subClassOf` edges, the instance layer typed by the KKO upper ontology (the TBox, vendored
separately — see `apps/sophos-reasoner/src/sophos_reasoner/data/PROVENANCE.md`).

This is **the vocabulary that `/api/graph/enrich` coherence-ranks against** and **the target
vocabulary semantic entity typing resolves entities into** (engine `mapEntityToKkoSemantic`,
0.4.37+). A drifted copy therefore does **not** produce an error — it produces *different
answers*: different coherence rankings, different entity types, and those results are written
back as content-addressed atoms that persist. That is the exact failure class this estate keeps
re-discovering, so this artifact is fail-CLOSED rather than fail-safe.

Loaded at startup behind `HELLGRAPH_LOAD_RC=on` (enabled in `deploy/values/hellgraph-service.yaml`).
Measured cost: ~560MB peak RSS with the 0.4.40 batched loader; the pod budget is 1Gi.

## Where the digest is ENFORCED
Two places, deliberately — one at runtime, one in CI, because either alone leaves a gap.

| where | what it checks | on failure |
|---|---|---|
| **runtime**, `src/server.ts::loadRcIfEnabled()` via `src/ontology-provenance.ts` | gz sha256, then inflated sha256 + byte count, before the first concept reaches the store | **refuses to load** — logs `RC load REFUSED`, service stays up with an empty RC set |
| **CI**, `scripts/check-ontology-digest.mjs` (run by `make engine-guards`, a `validate-target-diagnostics` matrix target) | the committed artifact still matches the pins recorded here and in `ontology-provenance.ts` | build fails |

CI catches a bad artifact before it ever ships; the runtime check catches a swapped file inside
a running image, which CI cannot see. Both read the same constants.

**Why both digests.** gzip is not reproducible — the same input under a different zlib version or
compression level yields different compressed bytes. So the gz digest can only ever prove "this
is the file we vendored"; it can never demonstrate equivalence to anything published upstream.
Only the **inflated** digest is portable provenance, and it is the one that ties these bytes to
`SocioProphet/kbpedia`.

**The override hole, closed.** `HELLGRAPH_RC_PATH` previously let an operator point the service at
any file, unverified. It now REQUIRES `HELLGRAPH_RC_SHA256` (64-hex, the gz digest); without it
the load is refused. An operator-supplied corpus is verified against the operator's own digest and
the log explicitly states that upstream equivalence is **not** claimed for it — we make no
provenance assertion about bytes we did not vendor.

Proven by `src/ontology-provenance.test.ts`, which tampers with a real gzip artifact and asserts
the verifier refuses — including a length-preserving tamper that survives a size check.

## License / attribution
KBpedia is released under **CC-BY-4.0**.
© Michael K. Bergman and Fred Giasson (Cognonto Corporation / KBpedia).
Attribution required; see <https://kbpedia.org> and <https://creativecommons.org/licenses/by/4.0/>.
This vendored copy preserves that attribution and does not modify the ontology content.
(The `SocioProphet/kbpedia` fork carries no `LICENSE` file of its own; the CC-BY-4.0 terms are
KBpedia's published licence for version 2.10 and are recorded here as the governing terms.)

## Re-vendoring
1. Download `versions/2.10/kbpedia_reference_concepts.zip` (or the newer version's) from the
   pinned `SocioProphet/kbpedia` commit.
2. `unzip -p <zip> kbpedia_reference_concepts.n3 | gzip -9 > ontology/kbpedia-rc-2.10.n3.gz`
3. Record BOTH digests: `shasum -a 256 ontology/kbpedia-rc-2.10.n3.gz` and
   `gunzip -c ontology/kbpedia-rc-2.10.n3.gz | shasum -a 256`.
4. Update `RC_GZ_SHA256`, `RC_N3_SHA256`, `RC_N3_BYTES`, `RC_SOURCE` in
   `src/ontology-provenance.ts` **and** the header above.
5. `node scripts/check-ontology-digest.mjs && npm test` — both must pass on the new digests.

---

# ImageSchemaNet cartridge — CLEAN-ROOM (authored, not vendored)

**File:** `imageschemanet.ttl` · **Namespace:** `https://ontology.socioprophet.ai/imageschemanet#`
**Status:** estate-authored SEED · **License:** **MIT** (ours — this is original work).

## What it is
The embodied-commonsense grounding layer: the image-schema taxonomy (CONTAINMENT,
CENTER_PERIPHERY, SOURCE_PATH_GOAL, PART_WHOLE, SUPPORT, BLOCKAGE), their spatial
primitives, the `:activates` property hierarchy, and a starter set of lexical activators.
Grounding function: `tools/imageschema_ground.py` (lexical unit / sentence → image schema).

## Why clean-room, not vendored
The reference implementation — **`StenDoipanni/ISAAC`** (ImageSchemaNet, the module network
of the paper below) — **ships no `LICENSE` file** (checked 2026-08-02; the GitHub license API
returns 404 and neither README declares terms). Under the estate's permissive-only rule,
absence of a licence = all-rights-reserved, so we do **not** copy or vendor its artifacts
(`isnet_correct.owl`, `isaac_improvements.ttl`, …). The **taxonomy and activation model are
uncopyrightable facts**, re-authored here from the open-access paper and cited.

## Source cited (not copied)
De Giorgis, Gangemi & Gromann, *"ImageSchemaNet: A Framester graph for embodied commonsense
knowledge"*, **Semantic Web 15 (2024) 1417–1441**, IOS Press — **CC-BY 4.0**. Taxonomy after
Johnson (1987) and Mandler & Pagán Cánovas (2014).

## Where it is ENFORCED
`make imageschemanet-grounding-check` (a `validate-target-diagnostics` matrix target):
structural conformance (every image schema has core spatial primitives; every activator
activates a known schema — fail-closed) + golden NL→image-schema groundings. Proven able to
go red by `tools/tests/test_imageschema_ground.py`.

## Growing it (later phases)
This SEED gives the grounding mechanism + starter activators. The full FrameNet/WordNet/VerbNet
activation set is P1-follow-on, populated via Framester alignment — authored/derived, still not
copied from the unlicensed repo. If upstream adds a permissive licence, re-evaluate vendoring.
