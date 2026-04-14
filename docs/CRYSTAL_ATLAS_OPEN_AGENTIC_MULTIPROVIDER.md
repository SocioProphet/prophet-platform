# Crystal Atlas in an open agentic multiprovider ecosystem

This document restates the Crystal Atlas lane for an **open, agentic, multiprovider ecosystem across all channels**.

It keeps the useful control-plane and distribution-plane separation from prior data-fabric thinking while extending the model beyond storage-to-storage transfer into:
- agent-to-agent exchange
- channel-to-channel delivery
- provider-neutral orchestration
- evidence-bearing replay across heterogeneous runtimes

## Core design constraints

### 1. Separate control from execution
Crystal Atlas execution workers should not decide *if* or *when* work happens.
They should execute a declared exchange, transformation, or enrichment plan and continuously report status, freshness, and technical metadata.

Control, policy, scheduling, routing, and governance belong to a higher control plane.
This keeps the runtime portable and makes provider choice replaceable.

### 2. Treat assets and channels as first-class
The old storage-centric distinction between data set, data asset, and data store remains useful, but Crystal Atlas needs a broader object model.

#### Asset classes
- structured dataset
- semi-structured document
- unstructured artifact
- conversation thread
- event stream
- graph edge bundle
- evidence receipt bundle
- agent output bundle

#### Channel classes
- web
- email
- chat
- voice
- SMS
- file/object storage
- queue/stream
- API/webhook
- repository/issue/PR workflow

Each asset should be individually addressable and replayable.
Each channel should declare delivery semantics, rate limits, formatting limits, and identity requirements.

### 3. Multiprovider means provider-neutral contracts
Crystal Atlas should not encode any single model vendor, storage vendor, queue vendor, or channel vendor into its core contracts.

Instead, every endpoint is described through a provider-neutral capability descriptor:
- identity/auth method
- read/write granularity
- supported content types
- latency/cost characteristics
- replay/idempotency guarantees
- transformation and masking support

### 4. Agentic does not mean opaque
Agents are actors in the system, not magic exceptions to governance.

Every agent invocation should carry:
- actor identity
- provider identity
- model/runtime identity
- tool/capability identity
- channel/source context
- policy decision trace
- evidence and receipt references

### 5. Transformations stay bounded
Crystal Atlas should support bounded transformations for transport and safe derivation:
- filtering
- masking
- pseudonymization
- projection
- schema mapping
- channel rendering
- policy-driven redaction

It should not collapse into a general-purpose arbitrary compute plane under the name of distribution.
That remains a separate compute/orchestration concern.

## Restated platform model

### Exchange kinds
The prior batch/sync split is still useful, but it is not sufficient for an agentic, channel-rich system.
Crystal Atlas should support at least these execution kinds:

#### SnapshotExchange
One-time or scheduled copy/derivation of an asset.
Examples:
- document to structured clause set
- graph edge bundle to search index
- contract pack to diligence report

#### SyncExchange
Continuous synchronization or CDC-style update.
Examples:
- repository issues to graph nodes
- CRM account updates to entitlement edges
- event stream to platform receipt catalog

#### SessionExchange
Interactive, stateful exchange across one or more channels.
Examples:
- agent conversation spanning web + email + Slack
- analyst workflow where upstream evidence is progressively refined
- guided diligence session with human review checkpoints

#### FanoutExchange
One source event or asset rendered and delivered to multiple channels/providers under policy.
Examples:
- diligence summary to dashboard + email + case record
- recommendation to chat + workflow ticket + API subscriber

### Endpoint model
Each source or destination is an endpoint, not just a storage adapter.
An endpoint may be:
- a datastore
- a channel connector
- an agent runtime
- a model provider
- a human review queue
- a workflow or case system

### Execution object
A generic execution object should declare:
- source endpoint and asset reference
- destination endpoint and asset/channel reference
- transformation and masking plan
- schedule or continuous/session mode
- retry and suspend policy
- routing and policy references
- status, freshness, and transfer/exchange statistics
- technical metadata refs
- receipt/evidence refs

## Why this matters for Crystal Atlas
Crystal Atlas is not just moving data between stores.
It is moving and transforming evidence-bearing assets across:
- multiple models/providers
- multiple agents
- multiple channels
- multiple storage and workflow systems

That means the lane has to optimize for:
- replayability
- provenance
- idempotency
- provider substitution
- channel-aware rendering
- policy-bounded publication
- tenancy and scoped joins

## Restated next two steps

### Step 1
Replace the narrow replay path with a **provider- and channel-neutral orchestration entrypoint**.

The current direction was to expose a replay route for the downstream contract-intel app. We should still do that, but the contract should be widened so it can accept a normalized upstream envelope from any provider or channel, not only a local file-backed payload.

Concretely:
- add a replay/orchestrate route that accepts a normalized Crystal Atlas event envelope
- require provider, channel, actor, and policy metadata in that envelope
- allow the adapter to resolve local state, queue payloads, webhook bodies, or channel artifacts through the same contract

### Step 2
Add **receipt/evidence emission and smoke tests that span representative providers and channels**.

The earlier plan was to add receipt/evidence emission for the adapter path and verify replay through HTTP. That remains correct, but the tests should now assert:
- provider identity is preserved
- channel identity is preserved
- masking/redaction decisions are recorded
- replay is idempotent
- downstream bundles remain queryable through the service API

Minimum smoke matrix:
- local state/file-backed source
- API/webhook-style source
- one conversational/channel-style source representation

## Design consequences for the current PR

The current PR should be understood as the first platform-native landing, not the final architecture.
It gives us:
- a visible contract family
- a downstream app scaffold
- an initial upstream adapter

The next slice should harden these pieces around the open agentic multiprovider assumptions above, rather than letting the lane harden around one provider, one channel, or one storage layout.
