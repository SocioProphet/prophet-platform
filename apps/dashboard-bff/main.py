from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import importlib.util
import os

ROOT = Path(__file__).resolve().parents[2]

# The SPA (socioprophet-web/client-vue) calls this bff cross-origin in deployment.
# In local dev the Vite proxy makes it same-origin; in production it is served
# behind a gateway or hits the bff directly, which needs CORS. Origins are
# env-configurable (comma-separated); default covers the local dev/preview ports.
_CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        'DASHBOARD_BFF_CORS_ORIGINS',
        'http://localhost:5173,http://localhost:4178',
    ).split(',')
    if o.strip()
]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


_contracts = _load_module(Path(__file__).with_name('contracts.py'), 'dashboard_bff_contracts')
OverviewResponse = _contracts.OverviewResponse
_producer = _load_module(ROOT / 'tools' / 'emit_intelligence_superiority_metrics.py', 'emit_metrics')
_vdt_producer = _load_module(ROOT / 'tools' / 'emit_vdt_metrics.py', 'emit_vdt_metrics')
_gyg_causal_producer = _load_module(ROOT / 'tools' / 'emit_gyg_causal.py', 'emit_gyg_causal')
_gyg_locations_producer = _load_module(ROOT / 'tools' / 'emit_gyg_locations.py', 'emit_gyg_locations')

app = FastAPI(title='dashboard-bff')

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=['GET', 'POST'],
    allow_headers=['*'],
)

@app.get('/health')
def health() -> dict:
    return {'service': 'dashboard-bff', 'status': 'ok'}

@app.get('/v1/overview', response_model=OverviewResponse)
def overview() -> object:
    return OverviewResponse(
        service='dashboard-bff',
        views=['overview', 'deepdive', 'cases', 'intelligence-superiority', 'value-drivers'],
        trace_required=True,
        evidence_required=True,
    )


def _fact_view(fact: dict):
    return _contracts.MetricFactView(
        provider_id=fact['provider_id'],
        model_release_id=fact['model_release_id'],
        value_scalar=fact['value_scalar'],
        sample_n=fact.get('sample_n'),
        source_trust_class=fact['source_trust_class'],
        reproduced_by_us=fact['reproduced_by_us'],
        scenario_id=fact.get('scenario_id'),
    )


@app.get('/v1/intelligence-superiority', response_model=_contracts.IntelligenceSuperiorityResponse)
def intelligence_superiority() -> object:
    """Serve the comparative-benchmark view from the schema-validated metric-facts producer. Grouped by
    metric with the trust provenance intact — the UI badges reproduced-by-us vs cited, and comparison_valid
    is set ONLY where a metric has both our facts and a comparable counterpart (never for a cite-only
    metric), so the frontend cannot render a head-to-head bar the data doesn't support."""
    bundle = _producer.build()
    defs = {d['metric_definition_id']: d for d in bundle['definitions']}
    by_metric: dict[str, dict[str, list]] = {}
    for f in bundle['facts']:
        m = by_metric.setdefault(f['metric_definition_id'], {'ours': [], 'cited': []})
        (m['ours'] if f['reproduced_by_us'] else m['cited']).append(_fact_view(f))

    metrics = []
    for mid, groups in by_metric.items():
        d = defs.get(mid, {})
        # a comparison is only valid where WE have a reproduced fact AND a comparable counterpart on the
        # SAME metric. Cite-only metrics (all frontier benchmarks here) are single-provider evidence.
        comparison_valid = bool(groups['ours']) and bool(groups['cited'])
        metrics.append(_contracts.MetricComparison(
            metric_definition_id=mid,
            metric_name=d.get('name', mid),
            family=d.get('family', 'task_performance'),
            ours=groups['ours'],
            cited=groups['cited'],
            comparison_valid=comparison_valid,
        ))

    n_repro = sum(len(m.ours) for m in metrics)
    n_cited = sum(len(m.cited) for m in metrics)
    return _contracts.IntelligenceSuperiorityResponse(
        service='dashboard-bff',
        metrics=metrics,
        headline_claim=(
            'On MMLU-STEM (n=450, reproduced), verified compute lifts an identical 7B from 0.611 baseline '
            'to 0.711 (+10pp, McNemar p=0.0002) — a technique win on the same model, not a claim of beating '
            'frontier models on frontier benchmarks.'
        ),
        reproduced_fact_count=n_repro,
        cited_fact_count=n_cited,
        disclaimer=(
            'Facts labeled internal_reproduced were measured by us; official_provider facts are cited '
            'vendor/leaderboard numbers we did NOT independently verify. Our metrics and cited metrics are '
            'disjoint by design — no cross-provider superiority is asserted on any single benchmark.'
        ),
    )


@app.get('/v1/vdt/catalog', response_model=_contracts.VdtCatalogResponse)
def value_driver_tree_catalog() -> object:
    """The industries the VDT endpoint can serve, so the surface can offer an industry selector
    without hard-coding the list."""
    return _contracts.VdtCatalogResponse(
        service='dashboard-bff',
        industries=[_contracts.VdtIndustry(**c) for c in _vdt_producer.catalog()],
    )


@app.get('/v1/vdt', response_model=_contracts.VdtResponse)
def value_driver_tree(industry: str = 'software') -> object:
    """Serve one industry's Value Driver Tree view from the canonical economic-prophet engine's OUTPUT.
    The value math (EP/UVMC/VDT identities) lives in economic-prophet and is NOT recomputed here — this
    endpoint reshapes the engine-produced artifact (tensor + computed uplifts, provenance intact) for the
    cockpit surface, which previously computed from a hand-mirrored TS fixture. `industry` selects the
    tensor (software / banks / energy); an unknown id falls back to software. epistemic_status travels
    with the payload so the UI presents the figure as a synthetic, machine-checked illustration."""
    v = _vdt_producer.build(industry)
    uplift = v['computed_total_value_uplift']
    frac = v['computed_value_uplift_fraction']
    ev = v['enterprise_value_baseline']
    return _contracts.VdtResponse(
        service='dashboard-bff',
        industry=v['industry'],
        scenario=v['scenario'],
        enterprise_value_baseline=ev,
        drivers=v['drivers'],
        domains=v['domains'],
        weights=[_contracts.VdtCell(**c) for c in v['weights']],
        per_kpi_contribution=[_contracts.VdtKpiContribution(**k) for k in v['per_kpi_contribution']],
        per_driver_uplift=v['per_driver_uplift'],
        per_domain_uplift=v['per_domain_uplift'],
        computed_total_value_uplift=uplift,
        computed_value_uplift_fraction=frac,
        projected_enterprise_value=v['projected_enterprise_value'],
        epistemic_status=v['epistemic_status'],
        provenance=v['provenance'],
        headline=(
            f"{v['industry']}: the modeled KPI levers project +${uplift / 1e6:.2f}M "
            f"({frac * 100:.2f}%) enterprise-value uplift on a synthetic ${ev / 1e9:.0f}B baseline — "
            f"machine-checked measurement from the economic-prophet engine, not a business outcome."
        ),
    )


@app.get('/v1/valuation/causal')
def valuation_causal(company: str = 'gyg') -> dict:
    """Serve the causal-graph valuation walk for a company (GYG use case, portfolio-manager persona).

    Joins the hellgraph supply-chain causal graph (supply-chain node -> causal edge -> value-driver KPI)
    with the economic-prophet VDT valuation (KPI -> driver -> enterprise-value uplift). Neither the graph
    topology nor the value math is computed here — both are read verbatim from their canonical artifacts
    with provenance intact (see tools/emit_gyg_causal.py). The GYG inputs are public-sourced; the payload
    carries epistemic_status, assumptions, limitations and evidence_refs so the surface presents an
    advisory measurement, never investment advice."""
    return _gyg_causal_producer.build(company)


@app.post('/v1/valuation/causal/recompute')
def valuation_causal_recompute(company: str = 'gyg', overrides: dict = Body(default={})) -> dict:
    """What-if recompute: apply the portfolio-manager's assumption overrides and RE-RUN the canonical
    economic-prophet engine (open_ep_framework.vdt.summarize_vdt), returning the same causal-walk payload
    with refreshed valuation and graph numbers. The value math is NOT re-implemented here — the engine is
    invoked live — so exploring assumptions cannot fork the value model.

    Body: {"ev_baseline": <number?>, "kpi_overrides": {"<kpi_name>": <delta_pct>}}"""
    return _gyg_causal_producer.recompute(overrides, company)


@app.get('/v1/locations')
def locations(company: str = 'gyg', q: str = '', state: str = '') -> dict:
    """GYG restaurant locations for the map + org digital-twin surface, with a MODELED per-site
    demographics/foot-traffic estimate. Locations are a public-sourced representative sample; the
    per-site sales estimate is anchored to GYG's DISCLOSED format AUV (drive-thru A$6.7m / strip A$5.0m)
    adjusted by a metro-density tier, and footfall is derived via average ticket — every record carries
    `basis` and the payload carries network_totals so the surface labels model vs measured. `q` filters
    by suburb/state/format; `state` filters by state code."""
    return _gyg_locations_producer.build(company, q, state)
