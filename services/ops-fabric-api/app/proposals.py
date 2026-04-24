from __future__ import annotations

from hashlib import sha256

from app.models import ActionProposal, ProposalImpact, ProposalRisk, WorkloadResourceSample


def _stable_id(sample: WorkloadResourceSample) -> str:
    material = f"{sample.target.id}|{sample.observed_at}|{sample.cpu_request_millicores}|{sample.cpu_p95_millicores}|{sample.memory_request_mib}|{sample.memory_p95_mib}"
    return "ops.proposal." + sha256(material.encode("utf-8")).hexdigest()[:16]


def build_rightsize_proposal(sample: WorkloadResourceSample) -> ActionProposal:
    cpu_after = min(max(sample.cpu_p95_millicores * 2, 100), sample.cpu_request_millicores)
    memory_after = min(max(sample.memory_p95_mib * 2, 128), sample.memory_request_mib)
    ratio = sample.cpu_p95_millicores / sample.cpu_request_millicores
    confidence = 0.82 if ratio < 0.25 else 0.72 if ratio < 0.5 else 0.55
    savings_ratio = max(0.0, 1.0 - (cpu_after / sample.cpu_request_millicores))
    monthly_savings = round(sample.monthly_cost_usd * savings_ratio, 2)

    return ActionProposal(
        proposal_id=_stable_id(sample),
        proposal_type="RIGHTSIZE_WORKLOAD",
        created_at=sample.observed_at,
        target=sample.target,
        summary=f"Report-only right-sizing proposal for {sample.target.id}.",
        rationale=[
            "Observed usage is below reserved capacity for the supplied sample window.",
            "The recommendation remains report-only in this slice.",
            "DevSecOps intelligence references are preserved for downstream review.",
        ],
        recommended_change={
            "mode": "REPORT_ONLY",
            "patch_kind": "ResourceIntent",
            "before": {"cpu_request_millicores": sample.cpu_request_millicores, "memory_request_mib": sample.memory_request_mib},
            "after": {"cpu_request_millicores": cpu_after, "memory_request_mib": memory_after},
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
            notes=["Report-only slice."],
        ),
        policy_status="NOT_EVALUATED",
        autonomy_tier="REPORT_ONLY",
        evidence_refs=sample.evidence_refs,
        intelligence_refs=sample.intelligence_refs,
    )
