# WordOps Phase-0 Implementation Checklist v0.1

## Track A - Naming, DNS, and Network

- [ ] Freeze product/repo namespace
- [ ] Provision DNS for public, private, auth, agents, and support surfaces
- [ ] Issue TLS certificates
- [ ] Define public edge network zone
- [ ] Define private core network zone
- [ ] Define service-to-service trust boundaries

## Track B - Public Matrix Edge

- [ ] Deploy Synapse public-edge
- [ ] Test public discovery rooms
- [ ] Establish public intake and support pathways

## Track C - Private Matrix Core

- [ ] Deploy Synapse private-core
- [ ] Configure service-side enforcement
- [ ] Create the first cases/agents

## Track D - Leased Resource Access

- [ ] Create first capability lease type
- [ ] Create initial trusted entities for access

## Track E - Security & Compliance

- [ ] Confirm encryption at rest for sensitive resources
- [ ] Test user identity management (OIDC)
- [ ] Ensure audit logging for agent actions

## Track F - Agentic Functionality

- [ ] Confirm initial agent integration
- [ ] Complete first automated case flow
- [ ] Verify decision-making logic in case execution

## Track G - Continuous Monitoring and Feedback

- [ ] Implement initial observability dashboard
- [ ] Create alerting for risk-based actions
- [ ] Test feedback collection for case handling
