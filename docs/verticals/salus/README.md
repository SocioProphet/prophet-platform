# SocioProphet Salus

SocioProphet Salus is the medical operating-system program inside the broader SocioProphet platform. It combines patient-owned data vaults, institutional interoperability, patient-state modeling, policy-governed clinical agents, professional intelligence, and care-execution routing into one evidence-first stack.

Salus is not a symptom chatbot, a publishing clone, a booking marketplace, or a dataset broker. It absorbs the useful parts of those categories while imposing stronger safety, dignity, provenance, and policy constraints.

## Naming

- **Umbrella**: SocioProphet Salus
- **Doctrine line**: *Salus Omnium*
- **Patient-facing care agent**: Cura
- **Professional workspace**: Ars Medica
- **Evidence layer**: Evidentia
- **Vault and consent substrate**: Arca Salutis
- **Policy and trust layer**: Aegis

## Product thesis

Salus exists to make practitioner-grade medical guidance globally accessible without turning medicine into spectacle, surveillance, or ad-driven manipulation.

The system is organized around five coupled planes:

1. trust, identity, and consent
2. clinical interoperability and vaults
3. patient-state and digital twins
4. decision support and agent orchestration
5. care execution, education, and research

## Core surfaces

### Patient agent (Cura)

The patient surface handles multimodal intake, symptom and injury reasoning, home triage, imaging/report interpretation assistance, follow-up, longitudinal tracking, and structured escalation into telehealth, clinic, urgent care, or emergency workflows.

### Professional workspace (Ars Medica)

The professional surface provides patient-context review, evidence cards, guideline and drug-reference support, calculators, workflow aids, recommendation trace inspection, documentation handoff, and education.

### Care routing and marketplace

We borrow the useful parts of scheduling marketplaces: insurance-aware routing, provider discovery, availability matching, pre-visit packet generation, and post-visit follow-up. Clinical routing must remain firewalled from marketplace incentives.

### Research and education

We support approved, purpose-bound access to de-identified or transformed medical assets for research, benchmarking, adjudication, curriculum, and professional training. Public curiosity is not a valid access purpose.

## Non-negotiable constraints

- no public gallery of patient media
- no raw-image monetization
- no ad-driven truth surfaces
- no single-model authority over clinical action
- no clinically material execution without policy checks, provenance, and auditable evidence

## Initial domain packs

- musculoskeletal and sports recovery
- nephrology
- wound and dermatology triage
- cardiometabolic monitoring
- imaging and report interpretation support

## Technical backbone

- FHIR, HL7 v2, X12, DICOM, and IHE at interoperability boundaries
- TriTRPC as the internal control and typed-event plane
- event-sourced evidence emission with replay semantics
- archetyped internal clinical model plus graph overlay
- hybrid reasoning stack: hard safety rules, pathway logic, fuzzy clinical grading, probabilistic risk models, multimodal perception, policy gates

## Why this lands in prophet-platform first

The available connector can create branches, files, and pull requests in existing repositories, but it cannot create a net-new GitHub repository from this chat. The immediate bootstrap therefore lands here, in `prophet-platform`, under a dedicated Salus namespace.

The extraction target remains a future dedicated repository:

`socioprophet-salus`

This bootstrap is intentionally structured so it can be lifted into that repository with minimal change.

## Immediate next work

1. formalize the pathway DSL
2. define the clinical event catalog
3. specify the role and purpose access matrix
4. implement the first musculoskeletal module
5. bind vault, evidence, and TriTRPC contracts into the broader platform
