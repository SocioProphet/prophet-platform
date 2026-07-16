# Knowledge Graph & Knowledge Engineering — SOTA Strategy V0

**Purpose:** an honest, grounded plan to make our graph / knowledge-engineering / extraction / representation genuinely best-in-class — not by out-building Neo4j at being Neo4j, but by winning on the axis none of them own. Grounded in what HellGraph *actually is today*, not the roadmap.

---

## 0. Honest self-assessment of the current KE surfaces

The Studio "Knowledge engineering" rail (Extraction · Ontology · Graph · Retrieval · Generation) is a **good frame and the right integration axis** — and it is now live-wired to real HellGraph stats. But it is **not yet SOTA knowledge engineering**: it is cards + actions + a BFF, not a Protégé-class ontology editor, a Neo4j-Bloom-class graph explorer, or a running extraction pipeline. The project graph is **empty (nodes:0)** — there is no real knowledge *in* it yet. So: the scaffolding is right; the substance is the work. This doc is that work.

---

## 1. What HellGraph actually is today (grounded)

**Real (`~/dev/hellgraph`):** `hg_kernel` (typed atoms, append-only valuations, journal, checkpoint, **deterministic replay**), `hg_proof` (**bounded-state proof checking + proof artifacts**; "proof is never silently downgraded to confidence"), `hg_runtime` (event/field/proof commit cycles). Epistemic-mode per value (`hypothesis|observed|derived|verified|attested|simulated`). Live service: `hellgraph-service` :8090 (`/api/graph/{stats,node,edge,query?label=,reason}` — label-query + PLN forward-chaining).

**Specified, NOT implemented:** RDF-star/SPARQL bridge; Cypher/GQL facade; the canonical 26-slot basis; vector/semantic retrieval bindings.

**So HellGraph's true nature:** a **proof-carrying, append-only, replayable graph kernel** — architecturally novel, early on query/tooling/scale. It is closer to an AtomSpace-style metagraph with a proof ledger than to a property-graph DB.

---

## 2. The field — what each does better (no flattery)

| System | What it does better than us, today |
|---|---|
| **Neo4j** | The mature property-graph DB: Cypher, the GDS algorithm library (centrality, community, pathfinding, embeddings), Bloom visualization, a native vector index + GraphRAG integrations, scale, and the largest ecosystem. The 800-lb gorilla. |
| **Protégé / WebProtégé** | The gold standard for OWL/RDF **ontology authoring** + DL reasoners (HermiT, Pellet, ELK), SHACL, collaborative web editing. Nobody authors ontologies better. |
| **Anzo (Cambridge Semantics)** | Enterprise RDF/SPARQL at scale + "graphmarts" data virtualization / graph data warehouse — federating many sources into one queryable graph fabric. |
| **Stardog** | Knowledge-graph platform: SPARQL + **reasoning** (OWL/SWRL/SHACL) + data virtualization + a semantic layer, enterprise-hardened. |
| **Ontotext GraphDB** | Mature RDF triplestore + reasoning + text/semantic search, RDF-star, big-triple scale. |
| **TypeDB (ex-Grakn)** | Strongly-typed schema + a logical **rule reasoner** over a hypergraph-ish model — expressive typed knowledge. |
| **TigerGraph / Neptune / Palantir Foundry** | Distributed graph scale (TigerGraph GSQL), managed multi-model (Neptune), and ontology-centric operational data (Foundry). |

**We do not out-mature any of them on query, reasoners, algorithms, visualization, or scale today.** Claiming otherwise would be a paper tiger.

---

## 3. The axis we own — and nobody else combines

Every incumbent gives you a *fast, mature graph*. **None of them gives you a graph you can prove, replay, and hand to an agent team under one governance scope.** Our defensible moat is the intersection:

1. **Proof-carrying / provenance-per-value.** Every value carries its `epistemic_mode` (`hypothesis→observed→derived→verified→attested→simulated`) + a proof artifact; proof is never silently downgraded to confidence. Neo4j/Anzo/Stardog store facts; **we store facts with their epistemic status and proof**. This is the "governed, verifiable knowledge" property no incumbent has as a kernel primitive.
2. **Deterministic replay.** The graph is an append-only, replayable ledger — you can reconstruct exactly how any conclusion was derived. Reproducible knowledge by construction (ties to the reproducible-science spine).
3. **Agent-native + fibered retrieval.** The graph is the substrate an agent swarm reasons over, with fibered (PageIndex ⊕ HellGraph) + graph-RAG retrieval *native*, not bolted on. Neo4j's GraphRAG is an add-on; ours is the point.
4. **One project scope for humans + agents.** The project `proj-` collection binds data, notebooks, models, ontology, graph, and retrieval — humans and agents read the same governed scope.
5. **Sovereign, unlicensed.** Neo4j Enterprise / Anzo / Stardog are expensive, cloud/enterprise-licensed. Ours is self-hosted, whole-stack-owned, data-never-leaves.

**Thesis:** *Neo4j is the graph database; Protégé is the ontology editor; Anzo is the graph fabric. We are the **proof-carrying, agent-native, sovereign knowledge graph** — where every fact has provenance and epistemic status, every derivation replays, ontology + extraction + retrieval + agents operate in one governed scope, and both humans and agents reason over it.* We beat them on **trust, governance, agent-nativeness, and sovereignty**, not raw query maturity — and we *interoperate* with their standards rather than reinvent them.

---

## 4. Strategy: INTEGRATE the standards, DIFFERENTIATE on the moat

Two-track. Don't rebuild reasoners and query engines that already exist — bridge to them; spend our build budget on the moat.

### Integrate (interoperability — so we're not an island)
- **RDF/SPARQL bridge on HellGraph** (already specified in `hg` — implement it): import/export RDF-star, answer a SPARQL subset. → interop with Protégé, Anzo, Stardog, GraphDB, the whole semantic web.
- **Ontogenesis as the schema/reason layer** (already built: RDF/OWL/JSON-LD modules + SHACL gates + `epi/` epistemology). Use it as the ontology authority ON TOP of HellGraph — we get Protégé-authored ontologies + SHACL validation without building an editor. Bridge `canon-to-ontogenesis` already exists in Noetica.
- **Import OWL ontologies** (Protégé/BFO/FIBO/domain) via ontogenesis `Alignments/`. Be a good semantic-web citizen.

### Differentiate (the moat — where the build budget goes)
- **Proof-carrying writes end-to-end:** every extraction/ingest writes atoms with `epistemic_mode` + proof artifact; the Studio surface *shows* provenance + epistemic status per fact (no incumbent surfaces this).
- **Replay/verify UX:** "how was this derived?" → replay the derivation from the journal. A verifiable-knowledge feature Neo4j can't offer.
- **Agent-native graph ops:** agents traverse/extend the project sub-graph via fibered retrieval; graph writes from agents carry `epistemic_mode: derived/simulated` and are gated.
- **Hybrid symbolic-vector:** the "eventual vector bindings" — wire HellGraph label/PLN + Noetica `sheafSearch`/`semanticSearch` into the fibered retriever (SP-RETR-FIBER-001) so retrieval is graph + vector + proof-graded in one call.

---

## 5. Remediation — make the KE real (phased, dependency-ordered)

| Phase | Deliverable | Beats |
|---|---|---|
| **KE-1** | **Real extraction → graph loop.** Wire a governed ingest (Holmes/doc-ingest) that writes entities/relations into HellGraph with `epistemic_mode` + proof, project-scoped. Populate the empty graph. | the empty-graph gap |
| **KE-2** | **Graph explorer surface** in Studio — live sub-graph view over `/api/graph/query`, entity/relation inspector, **provenance + epistemic-mode per node** (the differentiator, visible). | Neo4j Bloom (but provenance-first) |
| **KE-3** | **RDF/SPARQL bridge** on HellGraph + **ontogenesis OWL/SHACL** wired as the schema/validation layer; import a Protégé/FIBO ontology. | Protégé/Anzo interop |
| **KE-4** | **Fibered retrieval as a service** — HellGraph graph-walk + Noetica vector + proof-grade in one `/retrieve`, surfaced in Studio + callable by agents. | Neo4j GraphRAG (proof-graded, agent-native) |
| **KE-5** | **Replay/verify UX** — "derive path" for any fact; agent-written facts gated by epistemic-mode. | nobody |

**Start:** KE-1 (populate the graph for real) — because an empty graph makes every claim above vapor. Then KE-2 (see it, with provenance) is the visible proof we're different.

---

## 6. Honest bottom line

Today we are **behind** Neo4j/Protégé/Anzo on query maturity, reasoners, algorithms, visualization, and scale — and pretending otherwise is a paper tiger. But we are **architecturally ahead of all of them on the one axis that matters for trustworthy, agent-operated knowledge**: proof-carrying provenance, deterministic replay, agent-nativeness, and sovereignty. The plan is to *interoperate* with their standards (RDF/SPARQL/OWL/SHACL) so we lose nothing, and *spend our build budget* making the proof/provenance/agent moat real and visible. That is how our knowledge graph becomes not "another Neo4j" but the first knowledge graph you can **prove and hand to an agent team**.

---

## 7. Strategic doctrine (corrected 2026-07-16) — KKO upper ontology + meet-or-beat, THEN the moat

Two corrections that supersede the more concessive framing above:

**A. KKO / KBpedia is the estate's UPPER ONTOLOGY — the stack standard.** Not a bolt-on alignment; the top typology
everything types into. KKO (KBpedia Knowledge Ontology v1.60, CC-BY-4.0, ~58k reference concepts, Peirce's universal
categories) maps Noetica 1:1 (`~/dev/Noetica/agent-machine/canon/kko-alignment.json`, `lib/kko-bridge.ts`).
Crucially, **KKO formalizes our epistemic moat**: induced/deduced/abduced = Peirce's induction/deduction/abduction,
and the discovery process is `kko:Methodeutic`. So our provenance/epistemic-mode is **standards-grounded in a
formal open upper ontology, not proprietary**. Extraction types entities as `kko:Particulars` (Secondness);
ontogenesis + FIBO/gist sit *under* KKO. Every KG surface (extract, graph, RDF export, retrieval) types into KKO.

**B. MEET OR BEAT them on their turf, THEN overlay the moat.** The goal is not "behind but differentiated." It is
**parity + moat**: reach Cypher/GDS/reasoner/SPARQL/viz parity, *then* tag it with proof/provenance/agent-native/
sovereign. Per capability:

| Their capability | Our PARITY move | + Our MOAT overlay |
|---|---|---|
| Neo4j Cypher / GDS / Bloom | a graph query surface (Cypher/GQL facade) + PLN/graph algorithms + a force-directed explorer | provenance + epistemic-mode per node/edge |
| Protégé OWL + reasoners | ontogenesis OWL/SHACL under **KKO** upper ontology + a reasoner | proof-carrying, replayable derivations |
| Anzo / Stardog SPARQL + virtualization | HellGraph RDF/SPARQL bridge + federation | epistemic-mode triples survive export (KKO-grounded) |
| KBpedia | we ARE KKO-typed (parity by adoption) | + live extraction, agent-native, sovereign |

**Shipped toward this:** the RDF/Turtle export now types nodes into `kko:Particulars` and carries `sp:epistemicMode`
+ `prov:wasGeneratedBy` + `dct:source` — KKO-grounded interop that keeps the provenance every incumbent drops on
export. Next parity moves: graph query surface (Cypher/SPARQL), force-directed explorer, a reasoner over KKO.
