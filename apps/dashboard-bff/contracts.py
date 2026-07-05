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


class VdtCell(BaseModel):
    """One (value-driver × capability-domain) cell of the attribution tensor: the fraction of
    enterprise value carried by that intersection. The cells sum to ~1.0 for the industry."""
    driver: str
    domain: str
    weight: float


class VdtKpiContribution(BaseModel):
    """A KPI lever and the enterprise-value uplift it produces = improvement × cell weight × EV.
    polarity is carried so the UI can show that a falling lower_better metric is a positive move."""
    kpi: str
    driver: str
    domain: str
    delta_pct: float
    polarity: str
    value_contribution: float


class VdtResponse(BaseModel):
    """The Value Driver Tree view, served from the canonical economic-prophet engine's OUTPUT (never
    recomputed here — the value math lives in economic-prophet). The surface renders the driver×domain
    attribution heatmap (weights), per-driver/-domain uplift bars, and the KPI-lever cards; headline is
    the engine's computed total. epistemic_status + provenance keep the number honest about being a
    synthetic, machine-checked illustration rather than a measured business outcome."""
    service: str
    industry: str
    scenario: str
    enterprise_value_baseline: float
    drivers: list[str]
    domains: list[str]
    weights: list[VdtCell]
    per_kpi_contribution: list[VdtKpiContribution]
    per_driver_uplift: dict[str, float]
    per_domain_uplift: dict[str, float]
    computed_total_value_uplift: float
    computed_value_uplift_fraction: float
    projected_enterprise_value: float
    epistemic_status: dict
    provenance: dict
    headline: str
