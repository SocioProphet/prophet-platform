from typing import Optional   # explicit Optional (not 'X | None') so pydantic v2 resolves it on py3.9

from pydantic import BaseModel


class OverviewResponse(BaseModel):
    service: str
    views: list[str]
    trace_required: bool = True
    evidence_required: bool = True


class MetricFactView(BaseModel):
    """One metric-fact as the dashboard renders it — carries the trust provenance so the UI can badge
    'reproduced by us' vs 'cited, unverified' rather than presenting all numbers as equal."""
    provider_id: str
    model_release_id: str
    value_scalar: float
    sample_n: Optional[int] = None
    source_trust_class: str
    reproduced_by_us: bool
    scenario_id: Optional[str] = None


class MetricComparison(BaseModel):
    """All facts for one metric (= one benchmark). comparison_valid is TRUE only when the metric has BOTH
    our reproduced facts and an independently-comparable counterpart — otherwise it's a single-provider
    view (ours, or cited-only) and the UI must NOT draw a head-to-head bar."""
    metric_definition_id: str
    metric_name: str
    family: str
    ours: list[MetricFactView]
    cited: list[MetricFactView]
    comparison_valid: bool


class IntelligenceSuperiorityResponse(BaseModel):
    """The comparative-benchmark view. headline_claim is the ONLY superiority statement the data
    structurally supports (like-for-like, reproduced) — everything else is presented as separate
    single-provider evidence, never as a cross-provider 'we win'."""
    service: str
    metrics: list[MetricComparison]
    headline_claim: str
    reproduced_fact_count: int
    cited_fact_count: int
    disclaimer: str
