from app.models import EvidenceRef, IntelligenceRef, WorkloadResourceSample, WorkloadTarget
from app.proposals import build_rightsize_proposal


def sample() -> WorkloadResourceSample:
    return WorkloadResourceSample(
        target=WorkloadTarget(
            kind="Workload",
            id="sample-workload",
            namespace="default",
            cluster="p0-lab",
            zone="local",
        ),
        observed_at="2026-04-24T17:45:00Z",
        cpu_request_millicores=1000,
        cpu_p95_millicores=220,
        memory_request_mib=2048,
        memory_p95_mib=620,
        monthly_cost_usd=96.0,
        evidence_refs=[
            EvidenceRef(
                evidence_id="evidence.metric-window.0001",
                kind="METRIC_WINDOW",
                source="synthetic-v0",
                uri="memory://ops-fixtures/metric-window/0001",
                observed_at="2026-04-24T17:45:00Z",
            )
        ],
        intelligence_refs=[
            IntelligenceRef(
                intelligence_id="gdi.profile.operational-exhaust-fusion.v0",
                profile_ref="profiles/operational-exhaust-fusion-profile.v0.yaml",
                kind="OPERATIONAL_EXHAUST_FUSION",
                confidence=0.7,
            )
        ],
    )


def test_build_rightsize_proposal_is_report_only() -> None:
    proposal = build_rightsize_proposal(sample())
    assert proposal.proposal_type == "RIGHTSIZE_WORKLOAD"
    assert proposal.policy_status == "NOT_EVALUATED"
    assert proposal.autonomy_tier == "REPORT_ONLY"
    assert proposal.recommended_change["mode"] == "REPORT_ONLY"


def test_build_rightsize_proposal_preserves_intelligence_refs() -> None:
    proposal = build_rightsize_proposal(sample())
    assert proposal.intelligence_refs
    assert proposal.intelligence_refs[0].source_repo == "SocioProphet/global-devsecops-intelligence"
