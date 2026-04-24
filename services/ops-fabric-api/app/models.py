from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    evidence_id: str
    kind: str
    source: str
    uri: str
    observed_at: str
    digest: str | None = None
    notes: str | None = None


class IntelligenceRef(BaseModel):
    intelligence_id: str
    source_repo: str = "SocioProphet/global-devsecops-intelligence"
    profile_ref: str
    kind: str
    uri: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    notes: str | None = None


class WorkloadTarget(BaseModel):
    kind: str = "Workload"
    id: str
    namespace: str | None = None
    cluster: str | None = None
    zone: str | None = None


class TelemetryEvent(BaseModel):
    event_id: str
    event_type: str
    observed_at: str
    subject: WorkloadTarget
    source: dict[str, str]
    measurements: dict[str, int | float | str | bool | None] = Field(default_factory=dict)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    intelligence_refs: list[IntelligenceRef] = Field(default_factory=list)


class WorkloadResourceSample(BaseModel):
    target: WorkloadTarget
    observed_at: str
    cpu_request_millicores: int = Field(ge=1)
    cpu_p95_millicores: int = Field(ge=0)
    memory_request_mib: int = Field(ge=1)
    memory_p95_mib: int = Field(ge=0)
    monthly_cost_usd: float = 0.0
    evidence_refs: list[EvidenceRef]
    intelligence_refs: list[IntelligenceRef] = Field(default_factory=list)


class ProposalImpact(BaseModel):
    cost_delta_monthly_usd: float
    energy_delta_kwh_monthly: float | None = None
    slo_risk_delta: float
    security_risk_delta: float = 0.0
    confidence: float = Field(ge=0, le=1)


class ProposalRisk(BaseModel):
    blast_radius: str
    reversibility: str
    requires_human_approval: bool
    notes: list[str] = Field(default_factory=list)


class ActionProposal(BaseModel):
    proposal_id: str
    proposal_type: str
    created_at: str
    target: WorkloadTarget
    summary: str
    rationale: list[str]
    recommended_change: dict[str, object]
    impact_estimate: ProposalImpact
    risk: ProposalRisk
    policy_status: str = "NOT_EVALUATED"
    autonomy_tier: str = "REPORT_ONLY"
    evidence_refs: list[EvidenceRef]
    intelligence_refs: list[IntelligenceRef] = Field(default_factory=list)


class SearchRecord(BaseModel):
    result_id: str
    source: str = "OPS_FABRIC"
    entity_type: str
    title: str
    text: str
    target_ref: str | None = None
    evidence_ref_ids: list[str] = Field(default_factory=list)
    intelligence_ref_ids: list[str] = Field(default_factory=list)
    final_score: float = Field(default=1.0, ge=0, le=1)
