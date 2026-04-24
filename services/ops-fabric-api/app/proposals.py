from __future__ import annotations

from hashlib import sha256

from services.ops_fabric_api.app.models import ActionProposal, ProposalImpact, ProposalRisk, WorkloadResourceSample


def _stable_id(sample: WorkloadResourceSample) -> str:
    material = "|".join([
        sample.target.id,
        sample.observed_at,
        str(sample.cpu_request_millicores),
        str(sample.cpu_p95_millicores),
        str(sample.memory_request_mib),
        str(sample.memory_p95_mib),
    ])
    return "ops.proposal." + sha256(material.encode("utf-8")).hexdigest()[:16]


def build_rightsize_proposal(sample: WorkloadResourceSample) -> ActionProposal:
    cpu_after = max(sample.cpu_p95_millicores * 2, 100)
    memory_after = max(sample.memory_p95_mib * 2, 128)

    cpu_after = min(cpu_after, sample.cpu_request_millicores)
    memory_after = min(memory_after, sample.memory_request_mib)

    request_ratio = 0.0
    if sample.cpu_request_millicores:
        request_ratio = sample.cpu_p95_millicores / sample.cpu_request_millicores

    confidence = 0.55
    if request_ratio < 0.5:
        confidence = 0.72
    if request_ratio < 0.25:
        confidence = 0.82

    savings_ratio = 0.0
    if sample.cpu_request_millicores:
        savings_ratio = max(0.0, 1.0 - (cpu_after / sample.cpu_request_millicores))

    monthly_savings = round(sample.monthly_cost_usd * savings_ratio, 2)

    return ActionProposal(
        proposal_id=_stable_id(sample),
        proposal_type="RIGHTSIZE_WORKLOAD",
        created_at=sample.observed_at,
        target=sample.target,
        summary=f"Report-only right-sizing proposal for {sample.target.id}.",
        rationale=[
            "Observed resource usage is below reserved capacity for the supplied sample window.",
            "The proposal is report-only and must pass policy review before any later handoff.",
            "Intelligence references are preserved for DevSecOps and AI4IT context.",
        ],
        recommended_change={
            "mode": "REPORT_ONLY",
            "patch_kind": "ResourceIntent",
            "before": {
                "cpu_request_millicores": sample.cpu_request_millicores,
                "memory_request_mib": sample.memory_request_mib,
            },
            "after": {
                "cpu_request_millicores": cpu_after,
                "memory_request_mib": memory_after,
            },
        },
        impact_estimate=ProposalImpact(
            cost_delta_monthly_usd=-monthly_savings,
            energy_delta_kwh_monthly=None,
            slo_risk_delta=0.02 if savings_ratio > 0 else 0.0,
            security_risk_delta=0.0,
            confidence=confidence,
        ),
        risk=ProposalRisk(
            blast_radius="LOW",
            reversibility="ROLLBACK_PATCH",
            requires_human_approval=True,
            notes=["v0.1 produces report-only recommendations."],
        ),
        policy_status="NOT_EVALUATED",
        autonomy_tier="REPORT_ONLY",
        evidence_refs=sample.evidence_refs,
        intelligence_refs=sample.intelligence_refs,
    )
