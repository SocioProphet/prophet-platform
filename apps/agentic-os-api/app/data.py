"""Canonical agentic-OS objects served by the coordination service.

Shapes conform to the sourceos-spec agentic-OS contract (Opportunity / AgentPod /
ReadinessScore / CaptureCadence), which composes over prophet-workspace
(ProfessionalWorkroom / OrgGovControlRoom) and prophet-mesh (agent-choir + estate
graph). This is the seed dataset the service serves until a live registry adapter
resolves the same URNs from the workspace + estate graph.
"""
from __future__ import annotations

READINESS_DIMS = [
    "buyerProblem", "solutionHypothesis", "sharedLibraries", "agentPod", "partnerArchetype",
    "namedPartnerTargets", "oemLane", "artifactPack", "deltaControl", "questions", "pricing", "pastPerformance",
]

PODS = [
    {"id": "urn:srcos:agent-pod:capture-lead", "type": "AgentPod", "specVersion": "2.0.0",
     "role": "Capture Lead", "mandate": "Own pursuit strategy, buyer map, milestones, and decisions.",
     "inputs": ["signals", "updates", "Q&A", "competitive intel"],
     "outputs": ["pursuit plan", "gate decisions", "action backlog"],
     "repoAnchors": ["sociosphere", "socioprophet"], "status": "active", "choirRole": "governance-sentinel"},
    {"id": "urn:srcos:agent-pod:technical-solution", "type": "AgentPod", "specVersion": "2.0.0",
     "role": "Technical Solution", "mandate": "Design service model, architecture, transition, operating model.",
     "inputs": ["scope", "priorities", "reusable patterns"], "outputs": ["solution narrative", "architecture"],
     "repoAnchors": ["prophet-platform", "prophet-platform-standards"], "status": "active", "choirRole": "planning-agent"},
    {"id": "urn:srcos:agent-pod:evidence-qa", "type": "AgentPod", "specVersion": "2.0.0",
     "role": "Evidence / QA", "mandate": "Run review gates and coherence checks across all objectives.",
     "inputs": ["draft artifacts", "matrices"], "outputs": ["gate report", "defect list"],
     "repoAnchors": ["agentplane", "policy-fabric"], "status": "active", "choirRole": "governance-sentinel"},
]

CADENCE = {
    "id": "urn:srcos:capture-cadence:standard-8wk", "type": "CaptureCadence", "specVersion": "2.0.0",
    "name": "Standard 8-week capture sprint", "currentWeek": 4,
    "weeks": [
        {"week": 0, "objective": "Intake + normalize", "minReadiness": 0.2, "exitDecision": "pursue / watch / pause"},
        {"week": 4, "objective": "Artifact pack v1", "minReadiness": 0.5, "exitDecision": "Gate 1 complete"},
        {"week": 8, "objective": "Delta sprint", "minReadiness": 0.8, "exitDecision": "go-forward after delta"},
    ],
}


def _readiness(opp_slug: str, scores: dict[str, int]) -> dict:
    full = {d: scores.get(d, 0) for d in READINESS_DIMS}
    total = sum(full.values())
    pct = round(total / (len(READINESS_DIMS) * 3) * 100)
    rag = "Green" if pct >= 70 else "Amber" if pct >= 40 else "Red"
    return {
        "id": f"urn:srcos:readiness-score:{opp_slug}", "type": "ReadinessScore", "specVersion": "2.0.0",
        "opportunityRef": f"urn:srcos:opportunity:{opp_slug}", "dimensions": full,
        "total": total, "max": 36, "readinessPct": pct, "rag": rag, "nextGate": "Gate 1",
        "policyRef": "policy://capture/burden-of-proof/gate-1",
    }


OPPORTUNITIES = [
    {"id": "urn:srcos:opportunity:health-devsecops", "type": "Opportunity", "specVersion": "2.0.0",
     "name": "Health Services DevSecOps", "cluster": "Health", "missionOwner": "PDS",
     "buyingProblem": "Sustain legacy health apps while modernizing safely outside the Oracle Health baseline.",
     "deliveryPattern": "Continuity-plus-modernization delivery cell; governed DevSecOps.",
     "reuseRepos": ["prophet-platform", "agentplane", "policy-fabric"],
     "podRefs": ["urn:srcos:agent-pod:capture-lead", "urn:srcos:agent-pod:technical-solution", "urn:srcos:agent-pod:evidence-qa"],
     "workroomRef": "workroom://health-devsecops", "controlRoomRef": "controlroom://health-devsecops",
     "telos": {"objective": "Intelligence serves human flourishing", "constraints": ["non-domination", "consent", "dignity"]},
     "readinessRef": "urn:srcos:readiness-score:health-devsecops", "status": "Active",
     "winTheme": "We preserve continuity while industrializing governed modernization."},
    {"id": "urn:srcos:opportunity:zta-acceleration", "type": "Opportunity", "specVersion": "2.0.0",
     "name": "ZTA Acceleration", "cluster": "Cyber", "missionOwner": "OIS",
     "buyingProblem": "Accelerate zero-trust across identity, network, and data without breaking operations.",
     "deliveryPattern": "Identity-control-plane cell with runtime identity semantics and evidence refs.",
     "reuseRepos": ["mcp-a2a-zero-trust", "policy-fabric"],
     "podRefs": ["urn:srcos:agent-pod:technical-solution", "urn:srcos:agent-pod:evidence-qa"],
     "workroomRef": "workroom://zta-acceleration", "controlRoomRef": "controlroom://zta-acceleration",
     "telos": {"objective": "Intelligence serves human flourishing", "constraints": ["non-domination", "consent", "dignity"]},
     "readinessRef": "urn:srcos:readiness-score:zta-acceleration", "status": "Active",
     "winTheme": "Zero trust as a governed control plane with evidence at every grant."},
]

READINESS = {
    "health-devsecops": _readiness("health-devsecops", {"buyerProblem": 3, "solutionHypothesis": 2, "sharedLibraries": 3, "agentPod": 2, "partnerArchetype": 2, "oemLane": 1, "artifactPack": 2, "deltaControl": 2, "questions": 1}),
    "zta-acceleration": _readiness("zta-acceleration", {"buyerProblem": 3, "solutionHypothesis": 2, "sharedLibraries": 3, "agentPod": 2, "oemLane": 1, "artifactPack": 2, "deltaControl": 2}),
}


def opp_slug(opp: dict) -> str:
    return opp["id"].rsplit(":", 1)[-1]
