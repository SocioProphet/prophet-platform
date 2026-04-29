# Professional Intelligence OS

## Purpose

Professional Intelligence OS is the SocioProphet product spine for governed institutional work. It turns the existing platform, workspace, policy, agent, model, memory, contract, search, ontology, and DelEx repositories into one executable system for high-trust organizations.

This is not a clone of any vertical SaaS product. It is the trust-native operating layer for institutions that need governed AI, relationship intelligence, compliance, workflow execution, evidence, and measurable adoption.

## Category thesis

Professional firms and regulated institutions do not need generic chat layered over documents. They need institution-aware AI that can operate across relationships, matters, deals, contracts, obligations, policies, permissions, revenue workflows, and evidence trails.

The durable platform asset is the institution context engine: a governed compilation of institutional knowledge, role semantics, relationship graph, playbooks, obligations, policy constraints, access boundaries, decision history, and runtime evidence.

## Core capabilities

1. Institution Context Engine
   - Compiles institution-specific context from graph, workspace, memory, policy, contracts, catalog, and search surfaces.
   - Produces scoped context packs for agents, users, workspaces, and playbooks.
   - Must respect RBAC, ABAC, ReBAC, policy constraints, and workspace boundaries.

2. Institution Graph
   - Canonical graph of people, organizations, clients, matters, deals, assets, funds, relationships, contracts, obligations, workspaces, decisions, evidence, and agent runs.
   - Provides the substrate for conflicts, relationship intelligence, diligence, client/matter/deal context, and real-assets workflows.

3. Agent Fabric
   - Governed agent execution using Agentplane, Agent Registry, Model Router, Guardrail Fabric, Memory Mesh, and Model Governance Ledger.
   - Agents are workflow actors with purpose, tool grants, data scopes, policies, evals, approvals, audit logs, and replay evidence.

4. Conflict Engine
   - Detects and routes potential conflicts across entities, matters, deals, employee interests, restricted lists, ownership structures, relationship constraints, and AI/data-use policies.
   - Produces reviewable conflict reports and evidence receipts.

5. Obligation Ledger
   - Converts contracts, client terms, outside guidelines, data-use restrictions, billing rules, confidentiality terms, and AI-use constraints into machine-readable obligations.
   - ContractForge owns contract/economic semantics; Policy Fabric owns executable policy overlays.

6. Ethical Walls and Information Barriers
   - Policy-aware access and retrieval boundaries for workspaces, documents, memory chunks, graph edges, agent tools, and model context.
   - Enforces information barriers before retrieval, tool execution, memory recall, or agent output release.

7. Workspace OS
   - Prophet Workspace is the professional workroom layer for clients, matters, deals, projects, funds, assets, and initiatives.
   - Workrooms contain documents, meetings, tasks, decisions, agents, obligations, policies, evidence, notes, search, and workflow state.

8. Adoption Telemetry
   - Measures whether workflows are used, trusted, edited, rejected, escalated, accepted, and producing business impact.
   - DelEx consumes this telemetry for KPIs, delivery boards, demo acceptance, repo readiness, and bounty/acceleration scoring.

9. Evidence Plane
   - Every material AI or workflow action should emit evidence: source references, policy checks, model/tool versions, permissions evaluated, approval path, output hash, timestamps, and replay metadata.

10. Vertical Packs
   - Legal, private capital, investment banking, consulting, accounting, real assets, public-sector, research, and nonprofit packs share the same platform substrate with domain-specific schemas, playbooks, policies, evals, and dashboards.

## Repo ownership map

- `SocioProphet/delivery-excellence*`: operating model, KPIs, boards, playbooks, readiness, bounties, and delivery evidence acceptance.
- `SocioProphet/prophet-platform`: runtime/deployment hub, service contracts, API surfaces, datastore wiring, evidence/adoption contracts, and GitOps integration.
- `SocioProphet/prophet-workspace`: user-facing workrooms and workspace application semantics.
- `SocioProphet/agentplane`: evidence-forward execution control plane.
- `SocioProphet/agent-registry`: agent identities, sessions, tool grants, revocation, and authority.
- `SocioProphet/model-router`: governed model routing and fallback policy.
- `SocioProphet/guardrail-fabric`: reusable guardrails for models, agents, RAG, tools, and deployments.
- `SocioProphet/model-governance-ledger`: model, dataset, eval, promotion, factsheet, compliance, and rollback evidence.
- `SocioProphet/memory-mesh`: governed recall/writeback, retrieval adapters, and memory service runtime.
- `SocioProphet/policy-fabric`: policy authoring, validation, packaging, replay, and executable policy overlays.
- `SocioProphet/contractforge`: contract lifecycle, obligations, economics, settlement artifacts, and temporal correction semantics.
- `SocioProphet/gaia-world-model` and `SocioProphet/orion-field-intelligence`: real-assets, geospatial, field intelligence, and Earth-context packs.
- `SocioProphet/ontogenesis`, `semantic-serdes`, `regis-entity-graph`, `lattice-forge`: ontology, graph, serialization, and query surfaces.

## Initial demo workflows

1. Legal new matter intake
   - Intake request, entity resolution, conflict screen, obligation review, wall recommendation, approval, workspace creation, and evidence receipt.

2. Private capital deal screening
   - Ingest target, enrich entity, map relationships, compare to thesis, detect restrictions/conflicts, generate sourced screening memo, route to partner.

3. Real-assets diligence
   - Asset intake, ownership graph, lease/contract obligations, geospatial/field context, environmental or operational risks, diligence memo, approval workflow.

4. Revenue integrity review
   - Work capture, billing guideline enforcement, prebill exceptions, realization risk, adjustment explanation, and partner review.

## Acceptance criteria

The first integrated slice is acceptable when it can:

- load a playbook from DelEx/InnerSource;
- resolve institution context from graph, memory, policy, contract, search, and workspace sources;
- execute a governed agent step through Agentplane or a local stand-in;
- enforce a policy or obligation before producing output;
- emit adoption and evidence events;
- create or update a Prophet Workspace workroom;
- expose enough runtime surface in `prophet-platform` for smoke testing.

## Non-goals

- Do not hard-code a single vertical workflow into the platform core.
- Do not bypass policy, wall, or evidence controls for demo speed.
- Do not treat chat as the product. Chat is one interaction mode over governed institutional workflows.
- Do not encode confidential third-party interview content. Use only public market understanding and independent architecture.
