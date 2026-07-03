# Prophet Data Catalog — Technical & Functional Design

**Version:** 0.1 — Pre-Implementation Design
**Status:** DRAFT — FOR REVIEW
**Custodian:** M.D. Heller / SocioProphet
**Scope:** prophet-platform (Crystal Atlas, Office Plane runtime) · prophet-workspace · evidence-intake-kernel
**Companion specs:** `docs/CRYSTAL_ATLAS_DATA_CATALOG.md`, `1SP_Metadata_Standards_v0_1`, `docs/strategy/professional-intelligence-os.md`, `docs/KMAAS_REPO_RESPONSIBILITY_MAP.md`

---

## 1. Purpose and Scope

This document defines the design for the **Prophet Data Catalog**: the unified metadata, dataset-registry, and governance control plane for the SocioProphet platform. It has three objectives, in priority order:

1. **Absorb the design goals of the DataHub end-user platform** (Anant Bhardwaj / MIT CSAIL): radical low-barrier-of-entry, a flexible data store, an application ecosystem for data-processing tasks, first-class versioning, and frictionless sharing/collaboration — re-expressed natively on Prophet primitives.
2. **Interoperate outward** with the external metadata ecosystem — **CKAN**, the **DataHub Project** (ex-LinkedIn / Acryl), and **OpenMetadata** — through **open metadata standards** (DCAT / DCAT-US, schema.org/Dataset, Croissant, DataCite, Dublin Core), so Prophet datasets are discoverable, harvestable, and pushable to and from the wider data world.
3. **Publish to CK.org (Community Knowledge)** — the SocioProphet public commons, modeled on **Zenodo but enhanced**: concept + version DOIs, communities/collections, citation export, and OAI-PMH harvesting, *plus* the verified-compute / evidence-graded provenance Zenodo cannot carry. CK.org is the public distribution surface for `open` and `public_derived` assets and the outward face of the Alexandrian Academy / Knowledge Commons north-star.
4. **Out-class the incumbent governance catalogs** — **Collibra** and **IBM Watson Knowledge Catalog / watsonx.data intelligence** — not by copying their feature checklist, but by carrying something neither can: **verified-compute receipts, graded evidence (E1–E5), and forensic chain-of-custody** as first-class catalog metadata, while remaining sovereign, open, and interoperable rather than proprietary and lock-in.

A non-negotiable design rule, inherited from `1SP_Metadata_Standards_v0_1`: **every asset that enters the catalog acquires an immutable identity, a cryptographic hash, a temporal record, and a provenance chain before any transformation, enrichment, or publication.** The catalog is not a passive index — it is the **control plane** through which assets are promoted across governance zones (WNZL Dirt-to-Diamond).

---

## 2. Context: Two "DataHubs" and the Competitive Field

### 2.1 The naming collision

There are two unrelated systems called DataHub, and the design must serve both relationships:

- **MIT CSAIL DataHub** (Bhardwaj et al., the source deck): *a hosted platform for organizing, managing, sharing, collaborating, and processing data.* Its thesis — **"the real challenge today is not the data itself, but an ecosystem for solving data-processing tasks that end-users can use."** We adopt its **product/UX design goals**.
- **DataHub Project** (ex-LinkedIn / Acryl Data — "the other one"): an open-source **metadata catalog** built on entity URNs, typed aspects, and Metadata Change Proposals/Events (MCP/MCE) served by GMS. We **interoperate** with it as an integration target.

### 2.2 The incumbents we must beat

| System | What it is | Core strengths (2025) |
|---|---|---|
| **Collibra Data Intelligence Platform** | Proprietary governance + catalog SaaS | Business glossary / semantic layer linking physical data to business terms; automated lineage (incl. self-hosted/air-gapped); AI governance cataloguing models/agents/use-cases across AWS/Azure/GCP/Databricks; data quality + observability; unstructured-data support via Deasy Labs acquisition |
| **IBM Watson Knowledge Catalog / watsonx.data intelligence** | Proprietary AI data catalog on Cloud Pak for Data | Data quality profiling (accuracy/completeness/consistency/uniqueness) with exception workflows; IBM Manta end-to-end lineage; **runtime policy enforcement** — dynamic masking / tokenization / selective encryption applied at access time by role/query-context, without duplicating data |

Both are **descriptive-and-monitoring** governance catalogs. They *describe* data, *classify* it, *track* its lineage, and (WKC especially) *enforce* access policy. Neither **proves the correctness or replayability of a computation**, and neither is sovereign or openly interoperable — they are cloud-locked and proprietary. That asymmetry is the basis of our superiority claim (Section 5).

### 2.3 CK.org — the Community Knowledge commons (Zenodo, enhanced)

Where Collibra/WKC are *internal enterprise* catalogs, **CK.org (Community Knowledge)** is the **public distribution surface** — SocioProphet's open commons for sharing, citing, and reusing knowledge assets. Its reference model is **Zenodo** (the CERN open-research repository): deposit a record, get a citable **DOI**, version it, group it into **communities**, and expose it for **OAI-PMH** harvesting under an explicit license and access right.

Prophet is already structurally Zenodo-aligned: `CatalogAsset` carries a **concept-persistent ID plus per-version DOIs** — exactly Zenodo's concept-DOI / version-DOI split — and the code lineage explicitly cites "MIT DataHub / Zenodo / CK-CMX." CK.org is therefore not a new model but the **public projection** of Crystal Atlas for `open` and `public_derived` assets.

"Enhanced" means CK.org carries what Zenodo cannot:

- **Verified-compute receipts + E1–E5 evidence grade** on every deposited record — a citation that proves not just *what* was deposited but *that its results are correct and replayable*.
- **Forensic provenance** (chain-of-custody) travelling with the public record.
- **Knowledge Commons communities** mapped to Alexandrian Academy corpora, with the **segmented-commons** rule preserved (licensed/external corpora never leak into the sovereign brain).
- **DataCite metadata** out (DOI minting standard) and **DCAT/schema.org** alongside, so CK.org records are simultaneously citable (DataCite), discoverable (schema.org/Dataset), and harvestable (OAI-PMH, DCAT).

---

## 3. Design Goals (absorbed from the DataHub deck, extended for Prophet)

| # | DataHub deck goal | Prophet expression |
|---|---|---|
| G1 | **Low barrier of entry** — non-technical users (the "journalist": data.gov → query across files → visualize) | End-user "Data" surface on Office Plane; ingest by drag-drop; auto-classification via `evidence-intake-kernel`; no schema knowledge required |
| G2 | **Flexible data store** (files, RDBMS, extensible backends) | Crystal Atlas `source-catalog-entry` `source_kind` enum already spans open_web/registry/filings/repository/crm/upload/api_webhook/queue_stream; backend-abstract `office-artifact` |
| G3 | **App ecosystem** (App Center, thrift SDK, 20+ languages, pluggable processing apps) | `workflow-catalog-entry` + `functional-service-registry` + `service-catalog.yaml` surfaced as a browsable **App Center**, governed by capability/policy contracts |
| G4 | **Versioning** | `CatalogAsset`/`CatalogAssetVersion` with concept-persistent IDs (DOIs), `immutableAfterPublication`; SourceOS `ReleaseSet.v1` |
| G5 | **Sharing / collaboration** | Office Plane `office-collaboration-thread`, `note.shareMode`, `workroom`; `sharing-modes.v0.1.yaml` |
| G6 | **Automate the data-science pipeline** by connecting apps | Workflow catalog + agent run-refs + reproducibility (`CatalogAutomation.reproduce_command`) |
| — | **(Prophet-only) Verified provenance** | E1–E5 evidence grade, verified-compute receipts, forensic chain-of-custody — has **no analog** in the deck or the incumbents |

---

## 4. What Exists Today (baseline)

The internal metadata model is already **richer than what CKAN or DataHub Project ship**; the gap is interop and surfacing, not core modeling.

**prophet-platform / Crystal Atlas** (`contracts/crystal-atlas/schemas/`)
- `source-catalog-entry`, `asset-catalog-entry`, `model-catalog-entry`, `workflow-catalog-entry`, `provider-capability`, `policy-decision` — six catalog families; 7-tier `distribution_class`.
- `apps/lattice-studio/src/lattice_studio/catalog.py` — `CatalogAsset`/`CatalogAssetVersion`, DOI persistent IDs, `immutableAfterPublication` (explicitly cites MIT DataHub / Zenodo / CK-CMX).
- `active_metadata.py`, `platform_records.py` — active-metadata ingestion → enriched `PlatformAssetRecord`.
- `apps/hellgraph-service/` — AtomSpace knowledge graph (`/api/graph/node|edge|query|reason`); `contracts/ontology/*.shacl.ttl`.
- `contracts/ReceiptCatalogEntry.v0.1.json`, `apps/evidence-receipts/`, `apps/lampstand/` — receipt/evidence ledger + file-based discovery.

**prophet-workspace / Office Plane** (`contracts/`)
- `office-artifact.schema.json` (sourceRefs/derivedRefs lineage, backend abstraction), `office-collaboration-thread`, `note`, `workroom`, `office-suggestion`; `mail`/`calendar`/`tasks`.

**evidence-intake-kernel**
- `content-artifact-catalog/v1` (SQLite + append-only JSONL ledger), `drive_routing_map.json` (17-domain taxonomy), `classifier_rules.v0.2.json`, `intake_sweep.py`, `drive_sync.py`.

**Forensic spine** (`1SP_Metadata_Standards_v0_1`)
- Canonical metadata object model: Identity / Integrity (BLAKE3 + SHA-256) / Temporal (three-time) / Provenance / Classification (evidence_class, **evidence_grade E1–E5**, security_label); WNZL Dirt-to-Diamond zones where **the catalog is the control plane**.

**Absent today:** any CKAN / DataHub Project / OpenMetadata / DCAT / schema.org binding; a unified catalog API/service; browse-search-faceting UX; runtime policy *enforcement* (distribution_class is metadata-only); data profiling/quality scoring; automated lineage harvesting.

---

## 5. Superiority Thesis: How Prophet Beats Collibra and Watson Knowledge Catalog

We do **not** win by matching their feature lists item-for-item — we win on three structural advantages they cannot replicate, while reaching parity on the table-stakes they currently lead.

### 5.1 Where we are structurally superior (defend and surface)

| Axis | Collibra / WKC | Prophet Data Catalog | Why they can't copy it |
|---|---|---|---|
| **Verified compute** | Monitor & describe AI models/use-cases (Collibra AI governance); enforce data policy (WKC) | **Prove** computations: verified-compute receipts bound to assets; replayable canonicalization spec + serializer version | Their governance layer *observes* pipelines; it has no deterministic verifier or replay fabric |
| **Evidence grading** | Trust scores, quality scores | **E1–E5 forensic grade** (Speculative→Corroborated) + FRE 901/902, NIST SP 800-86, ISO/IEC 27037 admissibility | No incumbent carries litigation-grade chain-of-custody as catalog metadata |
| **Sovereignty + interop** | Proprietary, cloud-locked, vendor lock-in | Open standards out (DCAT/schema.org), sovereign + OS-level in; runs air-gapped end-to-end | Their commercial model *is* the lock-in |
| **Authored canon as semantic layer** | Business glossary curated by stewards | Frontier-authored canon + KKO/KBpedia upper ontology + HellGraph KG | A glossary is hand-curated terms; our semantic layer is an upper-ontology-aligned, machine-reasoned graph |

The one-line positioning: **Collibra and IBM tell you *what* your data is and *who* may touch it; Prophet additionally proves *that a result is correct and how it was derived* — and hands the descriptive layer to the open ecosystem instead of locking it up.**

### 5.2 Where they currently lead — and how we reach and pass parity

These are conversion/feature gaps, not moat gaps. Each must be closed for the superiority claim to hold end-to-end:

1. **Runtime policy enforcement / dynamic masking** (WKC's strongest card). Today `distribution_class` and `access_policy` are *metadata only*. → Promote them to an **enforced policy decision point** in the Catalog Gateway: masking/tokenization/row-column filtering applied at read time by role + query-context, emitting a `policy-decision` receipt. We pass parity by making every enforcement decision *itself verifiable evidence* — something WKC's masking does not produce.
2. **Data quality / profiling** (both lead). → Add column-level profiling (completeness/uniqueness/accuracy/consistency) + sample stats to `asset-catalog-entry`, computed as a verified-compute job so the quality score carries a receipt (WKC's scores do not).
3. **Automated lineage harvesting** (Collibra/Manta auto-harvest from BI/warehouses). → Lineage connectors that read existing `sourceRefs`/`derivedRefs` + agent run-refs into a materialized, queryable lineage graph in HellGraph; surpass by grading each lineage edge with evidence (E1–E5).
4. **Stewardship workflows + business-glossary UX** (Collibra). → Surface authored canon + KKO as the glossary; add steward roles/approval flows on the WNZL zone-promotion gates we already have.
5. **Browse / search / marketplace UX**. → Wire Sherlock semantic index behind the Catalog Gateway; expose the App Center + dataset marketplace on the end-user Data surface.

---

## 6. Architecture

```
                          ┌─────────────────────────────────────────────┐
   End users / agents ───▶│  Data Surface (Office Plane) + App Center     │  G1,G3,G5
                          └───────────────────────┬─────────────────────┘
                                                  │
                          ┌───────────────────────▼─────────────────────┐
                          │        CATALOG GATEWAY (new)                  │  GMS-equivalent
                          │  read · search · lineage · policy-enforce     │
                          │  unifies the surfaces below into one catalog  │
                          └───┬───────────────┬───────────────┬──────────┘
        ┌─────────────────────┘               │               └─────────────────────┐
        ▼                                      ▼                                      ▼
┌───────────────┐              ┌──────────────────────────┐            ┌────────────────────────┐
│ Crystal Atlas │              │ evidence-intake-kernel    │            │ Office Plane (workspace)│
│ catalog families│            │ artifact catalog + ledger │            │ office-artifact / notes │
└───────┬───────┘              └─────────────┬────────────┘            └───────────┬────────────┘
        │                                    │                                      │
        └───────────────┬────────────────────┴──────────────────────────────────────┘
                        ▼
            ┌───────────────────────────┐        ┌──────────────────────────────────────┐
            │ MOAT LAYER                │        │ INTEROP + PUBLISH LAYER (new)          │
            │ verified-compute receipts │        │ DCAT / schema.org / Croissant / DataCite│
            │ E1–E5 evidence grade      │        │   ├─▶ CKAN (ckanext-dcat harvest/API)  │
            │ forensic chain-of-custody │        │   ├─▶ DataHub Project (MCP emitter/URN) │
            │ WNZL zone control plane   │        │   ├─▶ OpenMetadata (entity API)         │
            │ (rides every entry)       │        │   └─▶ CK.org (Zenodo-like deposit/DOI)  │
            └───────────────────────────┘        └──────────────────────────────────────┘
```

### 6.1 Canonical model — Crystal Atlas (keep)

Crystal Atlas remains the **single internal source of truth**. It is a superset of DCAT and the DataHub entity model, so external formats are *projections*, never the master.

### 6.2 Catalog Gateway (new) — the GMS-equivalent

A thin service that fronts the three storage surfaces as **one logical catalog**, exposing:
- **Read/Resolve** — fetch an asset/source/model/workflow entry by ID or URN.
- **Search** — Sherlock semantic index backend; faceting on distribution_class, domain, evidence_grade, freshness.
- **Lineage** — materialized graph from sourceRefs/derivedRefs + agent run-refs, served from HellGraph.
- **Policy enforcement (PDP)** — evaluate distribution_class + access_policy at read time; apply masking/filtering; emit `policy-decision` receipt.
- **Write/Register** — the single entry point onboarding and ingest call to register sources/assets (Section 8).

This is the missing seam both CKAN and DataHub Project assume exists, and it is the integration point the onboarding runtime already expects (`workspace_operations` adapters are currently fixture-only).

### 6.3 Interop layer (new)

DCAT (+ schema.org/Dataset, Croissant for ML) is the **lingua franca**. Map Crystal Atlas ↔ DCAT once; CKAN, DataHub, and CK.org then become thin projections:

| Crystal Atlas | DCAT / schema.org | DataHub Project | CKAN | CK.org / Zenodo (DataCite) |
|---|---|---|---|---|
| `asset-catalog-entry` (dataset) | `dcat:Dataset` / `schema:Dataset` | `urn:li:dataset:(platform,name,env)` + schema/ownership/lineage aspects | CKAN `package` | Zenodo **record** + version DOI |
| `concept-persistent ID` (DOI) | `dct:identifier` | dataset key | `package.id` | Zenodo **concept DOI** |
| `asset` file/distribution | `dcat:Distribution` | dataset `datasetProfile` / schemaMetadata | CKAN `resource` | record **file** |
| `source-catalog-entry` | `dcat:Catalog` / `dcat:DataService` | `urn:li:dataPlatform` / container | CKAN `organization` / harvest source | CK.org **community** |
| `model-catalog-entry` | Croissant / `schema:SoftwareApplication` | `urn:li:mlModel` | (custom) | Croissant record |
| `distribution_class` + `policy-decision` | `dct:accessRights` / ODRL | DataHub policy / tags | CKAN access controls | Zenodo access right (open/embargoed/restricted/closed) |
| **verified-compute receipt + E1–E5** | `prov:wasGeneratedBy` (PROV-O extension) | **custom aspect** (Prophet extension) | extra field | **enhanced citation** (DataCite + Prophet extension) |

The last row is the moat traveling outward: we emit standards-compliant provenance *and* a Prophet-specific verified-compute aspect that downstream systems can ignore safely but that proves our superiority where it is consumed. On CK.org it becomes an **enhanced citation** — a DOI whose record proves the result is correct and replayable, which is exactly the "Zenodo but enhanced" promise.

### 6.4 Moat layer (keep, surface)

Verified-compute receipts, E1–E5 grading, the forensic canonical metadata object model, and WNZL zone promotion (catalog as control plane) attach to every catalog entry and ride along — internally enforced, externally exported as PROV-O + Prophet aspects.

---

## 7. External Integration Detail

- **DataHub Project:** stand up a **REST/Kafka MCP emitter** that translates Crystal Atlas writes into Metadata Change Proposals against entity URNs, including a `prophetVerifiedCompute` custom aspect. Optionally run DataHub ingestion *recipes* in reverse to harvest external catalogs into Crystal Atlas as `source-catalog-entry` records.
- **CKAN:** CKAN's API is DCAT-native via `ckanext-dcat`. Publish a **DCAT catalog feed** from the Gateway (CKAN harvests it) and consume CKAN harvest sources into Crystal Atlas. Gives us open-data-portal reach (data.gov-style) — directly serving the deck's journalist persona (G1).
- **OpenMetadata:** map to its entity JSON schemas via the same DCAT bridge + its ingestion API.
- **CK.org (Community Knowledge):** the public publish target. The Gateway exposes a **Zenodo-compatible deposit API** (create record → attach files → mint concept + version DOI → assign community → publish) for assets whose `distribution_class` is `open` or `public_derived`. Records carry **DataCite** metadata for citation, **schema.org/Dataset** for discovery, an **OAI-PMH** endpoint for harvesting, and the Prophet **verified-compute + E1–E5** extension as an enhanced citation. Communities map to Alexandrian Academy / Knowledge Commons corpora; the segmented-commons rule blocks licensed/external corpora from publication.
- **Open standards baseline:** DCAT / DCAT-US 3, schema.org/Dataset, Croissant (ML datasets), **DataCite** (DOI minting), Dublin Core terms, PROV-O for lineage, OAI-PMH feed for CK.org and academic/Alexandrian-Academy corpora.

---

## 8. Serving the Onboarding Flow

The catalog is the **system of record the onboarding runtime writes into**. Onboarding is currently contract-first (workspace_operations runtime is in-memory, adapters fixture-only); the Catalog Gateway is the production write-path those adapters are waiting for.

### 8.1 KMaaS sequence (data plane → content onboarding → experience)

Per `KMAAS_REPO_RESPONSIBILITY_MAP.md`, onboarding begins with the **data plane**, then **content onboarding**, then **experience workflows**. The catalog is the data-plane backbone:

```
User/tenant initiates onboarding
   │
   ▼ CreateOperation (workspace_operations runtime)
Workroom created  ──────────────▶ register workroom context (workspace-context-record)
   │
   ▼ Connect sources  ──────────▶ Catalog Gateway.Register(source-catalog-entry)
                                     · assigns identity + integrity + provenance (1SP rule)
                                     · sets distribution_class, freshness_policy, capability_ref
   ▼ Content onboarding  ────────▶ evidence-intake-kernel intake_sweep
                                     · classify (classifier_rules) → route (drive_routing_map)
                                     · Catalog Gateway.Register(asset-catalog-entry, tenant_id)
                                     · WNZL: Landing → Examination → Integration zone promotion
   ▼ Evidence  ──────────────────▶ EventEnvelope + EvidenceReceipt + ReceiptCatalogEntry
   ▼ Experience  ────────────────▶ assets now searchable/usable in App Center + Data surface
```

### 8.2 Worked example — Legal new-matter intake (from `professional-intelligence-os.md`)

The platform's flagship onboarding workflow maps cleanly onto the catalog:

1. **Matter created** → workroom (`workroomType: matter`) + `workspace-context-record`.
2. **Documents ingested** → each becomes an `asset-catalog-entry` (tenant-scoped) with Identity/Integrity/Provenance sealed at intake (1SP rule).
3. **Entity resolution + conflict screen** → lineage edges + HellGraph entities; conflicts surfaced from cross-tenant catalog query (governed by distribution_class).
4. **Obligation review** → `policy-decision` receipts; restricted assets masked at read by the Gateway PDP.
5. **Workspace ready** → catalog drives search, the App Center exposes matter-specific processing apps, and every artifact carries an evidence grade — a litigation-defensible posture **neither Collibra nor WKC can produce** because they monitor rather than prove.

### 8.3 Contract bindings (already present, to be wired)

- `contracts/workspace/workroom.schema.json`, `contracts/workspace-context/workspace-context-record.v0.1.json`
- `contracts/workspace/workspace-source.{document|sheet|slide}.json`
- `contracts/crystal-atlas/schemas/source-catalog-entry.v0.schema.json`, `asset-catalog-entry.v0.schema.json`
- `src/prophet_platform/workspace_operations/` (adapters → Catalog Gateway write-path)

---

## 9. Gaps Closed by This Design

| Gap (from baseline) | Closed by |
|---|---|
| No external interop (the explicit ask) | Interop layer §6.3 / §7 (DCAT bridge → CKAN, DataHub, OpenMetadata) |
| No public commons / citable publishing | CK.org Zenodo-like deposit + DOI §2.3 / §7 |
| No unified catalog API/service | Catalog Gateway §6.2 |
| App ecosystem absent as product | App Center surfacing of workflow/service registries §3 G3 |
| No end-user low-barrier surface | Data Surface on Office Plane §6 / §8 |
| Runtime policy enforcement only descriptive | Gateway PDP with verifiable masking §5.2(1) |
| No data quality/profiling | Verified-compute profiling job §5.2(2) |
| No queryable lineage | Materialized HellGraph lineage §5.2(3) |
| No stewardship/glossary UX | Canon+KKO glossary on WNZL gates §5.2(4) |
| No browse/search | Sherlock behind Gateway §5.2(5) |

---

## 10. Phased Roadmap

- **Phase 0 — Bridge spec.** Author the DCAT ↔ Crystal Atlas mapping (formalize §6.3) + Prophet verified-compute PROV-O extension. *Deliverable: a versioned mapping contract.*
- **Phase 1 — Catalog Gateway (read/search/resolve).** Unify the three surfaces; wire Sherlock search; expose lineage from existing refs. Wire `workspace_operations` adapters to the write-path (serves onboarding).
- **Phase 2 — Interop emitters + CK.org publish.** DataHub MCP emitter + CKAN DCAT feed + harvest-in; CK.org Zenodo-compatible deposit + DataCite DOI minting + OAI-PMH feed. OpenMetadata follows.
- **Phase 3 — Enforcement + quality (beat WKC).** Gateway PDP with verifiable masking; verified-compute profiling; graded lineage harvesting.
- **Phase 4 — Surfaces (beat the deck + Collibra).** End-user Data surface, App Center, dataset marketplace, CK.org community UX, steward/glossary UX.

Discipline (per Total Superiority Roadmap): **surface and ship the moat before adding more capability.** The internal model already exceeds the competition; the work is conversion — Gateway, interop, enforcement, UX — not new modeling.

---

## Appendix A — Key File Index

| Concern | Path |
|---|---|
| Catalog families | `prophet-platform/contracts/crystal-atlas/schemas/*.schema.json` |
| Catalog doc | `prophet-platform/docs/CRYSTAL_ATLAS_DATA_CATALOG.md` |
| Asset/version model | `prophet-platform/apps/lattice-studio/src/lattice_studio/catalog.py` |
| Active metadata | `prophet-platform/apps/lattice-studio/src/lattice_studio/{active_metadata,platform_records}.py` |
| Knowledge graph | `prophet-platform/apps/hellgraph-service/` |
| Receipts/discovery | `prophet-platform/contracts/ReceiptCatalogEntry.v0.1.json`, `apps/{evidence-receipts,lampstand}/` |
| Onboarding runtime | `prophet-platform/src/prophet_platform/workspace_operations/` |
| Onboarding intent | `prophet-platform/docs/{KMAAS_REPO_RESPONSIBILITY_MAP,strategy/professional-intelligence-os}.md` |
| Office Plane | `prophet-workspace/contracts/workspace/*.json`, `contracts/notes/note.schema.json` |
| Artifact catalog + taxonomy | `evidence-intake-kernel/{catalog.py,drive_routing_map.json,classifier_rules.v0.2.json}` |
| Forensic metadata spine | `1SP_Metadata_Standards_v0_1` |
| Search index | `sherlock-search/docs/SEMANTIC_ENTERPRISE_INDEX.md` |
