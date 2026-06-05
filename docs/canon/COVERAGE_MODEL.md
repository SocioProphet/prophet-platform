# Canon Coverage Model v0.1

Canon Coverage is the first usable catalog surface for Canon Commons.

The purpose is not to list APIs. The purpose is to establish what the platform can responsibly know, assert, verify, aggregate, and expose about domains, topics, sources, evidence, and community state.

## Coverage question

For any domain or topic, Canon should answer:

- What do we claim to cover?
- What assertion types exist in this domain?
- What sources can support those assertions?
- What evidence contract validates them?
- What services own ingestion, normalization, verification, search, presentation, and receipt generation?
- What sharing modes are permitted?
- What gaps remain?

## Coverage dimensions

Canon Coverage tracks seven dimensions.

1. Domain: broad area of community or product intelligence.
2. Topic: narrower theme inside a domain.
3. Assertion type: what kind of claim may be made.
4. Source class: source category and authority level.
5. Evidence contract: required proof object or schema.
6. Sharing mode: permitted release mode after policy review.
7. Owner service: repo or platform service responsible for the lifecycle stage.

## Minimum domain set

- civic-government-public-records
- companies-kyb-entity-intelligence
- markets-macro-finance
- legal-regulatory-compliance
- geospatial-environment-infrastructure
- cyber-vulnerability-supply-chain-risk
- research-patents-science
- healthcare-life-sciences
- commodities-trade-logistics
- ai-model-governance-evaluation
- internal-workspace-repo-service-estate

## Minimum assertion types

- `entity_identity`
- `entity_relationship`
- `ownership_or_control`
- `location_or_geometry`
- `event_or_observation`
- `numeric_metric`
- `risk_or_score`
- `legal_or_policy_status`
- `document_citation`
- `model_or_eval_result`
- `source_attribution`
- `provenance_lineage`
- `coverage_gap`
- `admissibility_decision`

## Coverage states

- `planned`: domain or assertion exists as a planning target.
- `source_identified`: at least one plausible source exists.
- `contract_defined`: evidence or assertion contract exists.
- `fixture_backed`: example or synthetic fixture exists.
- `validator_backed`: validator or schema check exists.
- `ingest_backed`: ingestion path exists.
- `queryable`: searchable/queryable by user or service.
- `community_aggregate_ready`: aggregate release can be governed.
- `product_ready`: product packaging path is defined.

## Policy default

Default state is private or planned. No domain, topic, assertion, or contribution becomes community-visible merely because it exists in a repo.

Community visibility requires explicit sharing mode, aggregation eligibility, policy admission, and receipt generation.

## Relation to GAIA world claims

GAIA already models governed world claims with anchors, source evidence, temporal validity, uncertainty, policy status, attribution, provenance, and classification. Canon generalizes this discipline beyond geospatial claims so that every domain can track what assertions are admissible and what evidence is required.

## Relation to Ontogenesis

Ontogenesis provides the governed-intelligence object vocabulary: Entity, Anchor, Evidence, Claim, ProofCertificate, ExplanationTrace, VectorCandidate, PolicyDecision, RuntimeReceipt, LearningEvent, Revocation, SlashTopicProfile, and related objects.

Canon Coverage should use that vocabulary rather than inventing an incompatible claim model.
