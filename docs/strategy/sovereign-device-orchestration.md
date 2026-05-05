# Sovereign Device Orchestration Strategy

Status: planning specification
Owner surface: Prophet Platform / Fog Stack
Related estates: SourceOS, AgentPlane, Guardrail Fabric, Sherlock Search, Ontogenesis, SocioProphet UI

## 1. Competitive signal

Apple, Google, Samsung, Amazon, Home Assistant, Huawei, and Xiaomi are converging on smartphone-centered orchestration. The market is no longer just smart-home control. It is a whole-device command plane spanning phone, voice, web, watch, home hub, camera, appliances, vehicle, browser, and cloud account.

Recent Google Home/Gemini messaging shows the direction clearly: AI camera event understanding, crisper live streams, zoomed notification previews, Gemini voice upgrades, continued conversation, web-based Ask Home, natural-language camera-history search, and automation management from a browser. The limitation is equally clear: subscription gating, cloud dependency, Wi-Fi/internet dependency, regional and language constraints, and probabilistic assistant behavior.

Apple remains the strongest phone-native orchestration benchmark because iPhone is also the identity surface, proximity token, notification router, wallet, watch bridge, camera, health node, home key, car key, app runtime, and continuity anchor. Google is currently more aggressive on AI-native home intelligence. Samsung has the broadest appliance and TV graph. Amazon retains voice/routine reach but lacks a sovereign phone OS. Home Assistant is the strongest local-first reference model.

## 2. Positioning

The Prophet/Fog/SourceOS answer is not another smart-home app. The target is a sovereign orchestration substrate above proprietary ecosystems.

We should make Apple, Google, Samsung, Amazon, Home Assistant, Matter/Thread, browsers, shells, cars, wearables, local agents, and cloud services observable, governable, searchable, programmable, and provable.

## 3. Product thesis

Sovereign Device Orchestration is the governed control plane for human, device, home, browser, shell, agent, and cloud actions.

Every node, event, routine, command, automation, sensor reading, assistant decision, and actuation must be represented as a typed object with provenance, policy, capability scope, trust state, evidence receipts, and revocation semantics.

Natural language may propose automations. It must not be the only executable representation. Executable routines must be inspectable, versioned, diffable, testable, signed, revocable, and auditable.

## 4. Core architecture

### 4.1 Device graph

Represent phones, laptops, browsers, shells, home hubs, cameras, sensors, appliances, vehicles, watches, speakers, cloud accounts, and local agents as governed nodes.

Minimum node fields:

- stable node id
- display name
- node type
- ecosystem adapter
- owner/user boundary
- location scope, if known and policy-permitted
- capability set
- attestation state
- last-seen timestamp
- trust state
- policy labels
- revocation status

### 4.2 Event ledger

Every orchestration-relevant event must become a receipt.

Examples:

- camera event detected
- routine fired
- voice command heard
- assistant interpreted intent
- automation generated
- automation approved
- device state changed
- policy allowed, denied, or escalated
- agent attempted actuation
- user overrode decision
- adapter failed or degraded

Minimum receipt fields:

- receipt id
- event type
- subject node
- actor identity
- source adapter
- timestamp
- observed state before and after, if available
- confidence
- evidence links
- policy decision
- capability used
- lineage parent ids
- retention class
- redaction class

### 4.3 Adapter boundary

Adapters normalize proprietary ecosystems into the same contract.

Initial adapter families:

- Matter/Thread
- HomeKit/Home where integration is permitted
- Google Home/Nest surface via available APIs and user export paths
- SmartThings
- Alexa routines/devices where available
- Home Assistant
- Android intents and sensors
- Apple Shortcuts/App Intents handoff where available
- browser events
- local shell/SourceOS events

Adapters must be capability-scoped and revocable. They should not leak raw credentials into the platform. Secrets stay in system stores or dedicated secret managers.

### 4.4 Automation representation

Automations must compile into signed, inspectable policy objects.

Minimum routine fields:

- routine id
- natural-language description
- normalized trigger set
- preconditions
- actions
- allowed devices
- disallowed devices
- safety class
- required approval mode
- rollback behavior
- test fixture set
- policy package references
- signature and version

### 4.5 Agent actuation boundary

Agents may recommend actions, draft routines, explain events, search history, and propose remediation. Actual actuation must pass through AgentPlane capability checks, Guardrail Fabric policy gates, and a receipt-emitting execution path.

High-risk actions require explicit approval or narrow delegated authority. Examples include locks, alarms, cameras, vehicle controls, payments, identity tokens, health-relevant actions, OS mutation, and irreversible data deletion.

### 4.6 Search and explanation

Sherlock Search should index orchestration receipts so users can ask:

- Why did this device turn on?
- What changed before the outage?
- Which routine fired last night?
- What did the assistant infer from the camera event?
- Which agent touched this file/device/account?
- Which policy allowed this action?
- What did we deny, and why?

The answer must return evidence, not just text.

### 4.7 UI workbench

The SocioProphet UI should expose an Orchestration Workbench:

- device graph
- event timeline
- active routines
- policy decisions
- agent proposals
- approvals queue
- search box over receipts
- adapter health
- degraded mode banners
- provenance/evidence drawer

## 5. SourceOS implications

SourceOS should treat orchestration as a local-first OS responsibility, not a cloud afterthought.

Required SourceOS work:

- local event capture and durable queueing
- offline-safe receipt creation
- policy evaluation at the edge where possible
- adapter health supervision
- local identity binding to node DID
- local redaction and retention rules
- replay protection
- repair/reconciliation after reconnect
- signed sync to Prophet Platform/Fog Stack surfaces

## 6. Non-goals for first slice

- Do not try to replace Apple Home, Google Home, SmartThings, Alexa, or Home Assistant in the first tranche.
- Do not directly actuate high-risk home/security/device controls without policy and approval gates.
- Do not store raw camera video unless explicitly supported by an adapter and governed retention policy.
- Do not build opaque natural-language automations that cannot be represented as signed routines.

## 7. First vertical slice

The first demo-credible slice should use Home Assistant or a fixture adapter as the operational spine because it is local-first and testable.

Slice:

1. fixture/Home Assistant adapter emits device nodes and events
2. sourceos-syncd stores local receipts and sync state
3. Ontogenesis defines node/event/routine schemas
4. Guardrail Fabric evaluates policy decisions
5. AgentPlane gates an agent-proposed routine
6. Sherlock indexes receipts and answers evidence-backed queries
7. SocioProphet UI shows device graph, event timeline, routine proposal, and evidence drawer

## 8. Acceptance criteria

- Device nodes can be registered from fixture data.
- Events produce typed receipts with provenance and policy fields.
- A natural-language automation can be compiled to an inspectable routine object.
- A policy gate can deny or require approval for high-risk actuation.
- Sherlock can answer at least five evidence-backed orchestration questions.
- UI can show device graph, event timeline, adapter status, and evidence details.
- All core contracts are testable without live proprietary ecosystems.

## 9. Repo mapping

- prophet-platform: orchestration API contracts, receipt envelope, bundle registration, integration spec
- sourceos-syncd: local-first device graph, event ledger, repair/replay/sync semantics
- ontogenesis: OWL/SHACL/JSON Schema/Avro-compatible schemas for devices, routines, events, receipts
- agentplane: capability-scoped actuation contract and agent proposal boundary
- guardrail-fabric: home/device policy pack and safety classifications
- sherlock-search: orchestration receipt indexing and evidence-backed query templates
- socioprophet: Orchestration Workbench UI

## 10. Strategic standard

Our standard should be stricter than Apple/Google/Samsung/Amazon on auditability and broader than Home Assistant on governed cross-domain orchestration.

The differentiator is not device count. The differentiator is provable cybernetic control: every perception, decision, routine, action, denial, override, and repair is modeled, searchable, governed, and reproducible.
