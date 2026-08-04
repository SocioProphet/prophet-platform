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


class VdtIndustry(BaseModel):
    """One selectable industry the VDT endpoint can serve."""
    id: str
    label: str
    industry: str


class VdtCatalogResponse(BaseModel):
    """The industries available at /v1/vdt — drives the surface's industry selector."""
    service: str
    industries: list[VdtIndustry]


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


class RiskFactView(BaseModel):
    """One governed risk / EP / inflation fact with its trust provenance, so the UI can badge
    'reproduced by us' vs 'reconstructed methodology' rather than presenting all numbers as equal."""
    name: str
    value: float
    unit: str
    source_trust_class: str
    reproduced_by_us: bool
    reconstructed: bool = False


class RiskEpFactsResponse(BaseModel):
    """Governed portfolio risk / economic-profit / alternative-inflation facts for the credit-risk
    visualization thesis. Risk/EP facts are reproduced from economic-prophet's model; the
    alternative-inflation facts are reconstructed (vendor series proprietary) and flagged as such."""
    service: str
    portfolio_id: str
    facts: list[RiskFactView]
    detail: dict = {}
    provenance: dict


class BoardEvidence(BaseModel):
    label: str
    href: str


class BoardCompetitor(BaseModel):
    """One competitor column on a litmus board. No 'estate' entry lives here — see BoardCellView."""
    id: str
    name: str
    note: Optional[str] = None


class LitmusFeatureView(BaseModel):
    id: str
    name: str
    definition: str


class BoardCellView(BaseModel):
    """One (feature x competitor) verdict. The board's scoring model is deliberately RELATIVE-ONLY: a
    cell states the estate's claim about its standing against THAT ONE competitor on THAT ONE feature
    (BEAT/MEET/PARTIAL/GAP) — the same feature legitimately carries a different verdict against a
    different competitor (e.g. BEAT vs Vectara, MEET vs Cohere on the same row). There is no
    independently-assessed absolute rank for either side, so there is no separate 'estate column' — every
    cell already IS the estate's claim, which is why evidence/maturity/basis live on every cell, not on
    a subset of them."""
    feature_id: str
    competitor_id: str
    rank: str
    evidence: Optional[BoardEvidence] = None
    maturity: Optional[str] = None
    basis: Optional[str] = None
    note: Optional[str] = None
    # Mirrors the emitter's own honesty flag (emit_intelligence_superiority_board._expand_score):
    # a thin BEAT/MEET lead (maturity=='spec' OR fewer than MIN_EVIDENCE_REFS evidence pointers) is
    # REQUIRED by validate_intelligence_superiority_board to set this, on pain of rejection. Dropping
    # it here would let the API serve a thin lead indistinguishable from a solid one.
    provisional: bool = False


class CategoryBoardView(BaseModel):
    id: str
    name: str
    description: str
    competitors: list[BoardCompetitor]
    features: list[LitmusFeatureView]
    cells: list[BoardCellView]


class CompetitiveBoardsResponse(BaseModel):
    """Served from tools/emit_intelligence_superiority_board.py's sealed, validator-gated dataset.

    NOT the same system as /v1/intelligence-superiority: that route serves numeric ML benchmark metrics
    (MMLU-STEM, GPQA, ...) with reproduced-vs-cited provenance. This route serves the categorical
    competitor litmus board (BEAT/MEET/PARTIAL/GAP per feature per named competitor). The two share an
    "intelligence-superiority" name by historical accident, not by design — do not conflate them."""
    service: str
    version: str
    generated_at: str
    estate_label: str
    categories: list[CategoryBoardView]
    disclaimer: str
