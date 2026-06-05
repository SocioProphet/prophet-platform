# Canon Commons Architecture v0.1

Canon Commons is the community intelligence layer of Prophet Platform.

It is not a raw data-sharing pool. It is a reciprocal, privacy-preserving data commons where members gain default access to governed aggregate knowledge produced from admissible community contributions, without gaining access to raw member data.

## Core thesis

Community membership should make the community understandable to itself.

Members contribute local, operational, domain, workflow, and product signals. Canon converts eligible contributions into anonymized, aggregated, policy-admitted community intelligence. The output is not another private data lake. The output is governed shared understanding: coverage, benchmarks, trends, gaps, risks, needs, capabilities, and evidence-backed assertions.

## Data compact

Canon Commons follows a compact.

- Raw data remains local, tenant-bound, private, client-owned, licensed, or permissioned unless explicitly published.
- Aggregate community intelligence is shared by default only after policy admission.
- No member receives another member's raw private data by default.
- Each shared aggregate carries method, provenance class, confidence, freshness, policy status, and receipt metadata.
- Small-cell leakage, re-identification, and hidden extraction are disallowed by design.

## Layers

### 1. Contribution layer

Members, organizations, agents, repos, workspaces, devices, datasets, workflows, and product surfaces generate contribution signals.

Contribution signals may include source availability, dataset metadata, task frequency, benchmark metrics, model/eval outcomes, workflow events, domain coverage, product feedback, entity observations, and operational health.

### 2. Admissibility layer

Canon decides whether a contribution may be used outside the private boundary.

Admission checks include source rights, consent, privacy class, aggregation threshold, re-identification risk, license class, freshness, provenance strength, confidence, purpose limitation, and product eligibility.

### 3. Community intelligence layer

Approved contributions become community-safe aggregates:

- domain and topic coverage;
- community benchmarks;
- assertion coverage;
- source coverage;
- common workflow/task demand;
- risk and compliance gap patterns;
- market and operational trends;
- product-fit signals;
- evidence and provenance quality distributions.

### 4. Workbench and product layer

Sherlock, Holmes, SynapseIQ, SocioSphere, Workroom, GAIA, and Prophet Platform surfaces expose Canon Commons by question, topic, domain, entity, geography, time, assertion type, source class, confidence, and admissibility status.

## Sharing modes

Canon Commons uses explicit sharing modes.

- `private_only`: visible only to owner or tenant.
- `aggregate_eligible`: may contribute to community aggregate if thresholds pass.
- `benchmark_eligible`: may contribute to peer comparison if cohort rules pass.
- `research_eligible`: may contribute to anonymized research outputs.
- `product_eligible`: may contribute to commercial or open data products after policy review.
- `public`: directly visible or redistributable according to source terms.

## Mandatory safeguards

Canon Commons requires:

- minimum aggregation thresholds;
- suppression or bucketing for sparse cells;
- privacy-class tracking;
- source-license tracking;
- purpose-bound access;
- receipt generation for aggregation and publication;
- explicit policy status on every community assertion;
- revocation and retraction paths;
- human review for sensitive or borderline release decisions.

## Non-goals

Canon Commons is not a surveillance layer, not a data broker, not a raw cross-tenant query fabric, not an advertising identity graph, and not a mechanism for reconstructing member behavior.

The community data layer must be reciprocal and governed: members participate to understand the community, not to exfiltrate one another's data.
