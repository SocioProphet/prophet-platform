# KKO — KBpedia Knowledge Ontology (vendored into owl-reasoner)

**File:** `kko-2.10.n3` · **SHA-256:** `d907919fb40f20ed39a7fde0e8d114027449d9354a1976ce8248db5634cb7b07`
**KKO version:** v2.00 · **Namespace:** `http://kbpedia.org/ontologies/kko#`

Vendored as **package data** (under `src/`, so it ships in the image the Dockerfile builds from `COPY src`).
It is the same byte-identical KKO TBox the HellGraph engine vendors (see
`~/dev/hellgraph/ontology/kko/PROVENANCE.md`), loaded here by `reasoner.py::_kko_tbox()` so that
`reason(..., with_kko=True)` computes RDFS/OWL-RL closure over the real KKO subClassOf hierarchy.

**Source:** sovereign fork `SocioProphet/kbpedia` @ `master`, `versions/2.10/kko-demo.n3`
(upstream `KBpedia/kbpedia`, formerly Cognonto).

**License:** CC-BY-4.0 — © Michael K. Bergman & Fred Giasson (Cognonto / KBpedia). Attribution preserved;
content unmodified. <https://kbpedia.org> · <https://creativecommons.org/licenses/by/4.0/>
