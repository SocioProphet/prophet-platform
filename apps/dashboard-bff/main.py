from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import importlib.util
import os
import re
import sys

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
    # dataclasses on 3.12 resolve cls.__module__ via sys.modules; a module loaded this
    # way must be registered before exec_module or that lookup silently returns None
    # (AttributeError: 'NoneType' object has no attribute '__dict__') for any @dataclass
    # the loaded file defines. None of the existing producers hit this; the board
    # validator does.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# One broken producer must not crashloop the whole BFF. contracts.py is REQUIRED (fail closed
# if it can't load — the response models are core to every endpoint); the tool producers below
# are each used by ONE endpoint, so a producer that fails to import degrades only its endpoint
# (a loud 503 naming the import error) and every other endpoint keeps serving. Failures are
# surfaced in the startup log, never swallowed — the arcticdb/compute-gateway silent-down lesson:
# a service that dies whole because one optional dependency is missing is a fragility, not safety.
_FAILED_PRODUCERS: dict[str, str] = {}


class _FailedProducer:
    """Stands in for a producer module that failed to import. Any attribute access — an
    endpoint reaching for `.emit()` — raises a 503 naming the producer and the underlying
    error, so the endpoint fails honestly while the service stays up."""

    def __init__(self, name: str, error: BaseException) -> None:
        self._name = name
        self._error = f'{type(error).__name__}: {error}'

    def __getattr__(self, _attr: str):
        raise HTTPException(status_code=503,
                            detail=f"producer '{self._name}' unavailable: {self._error}")


def _try_load(rel_tool: str, name: str):
    """Load a per-endpoint producer resiliently — the module on success, else a
    _FailedProducer sentinel (recorded in _FAILED_PRODUCERS) so boot never fails."""
    try:
        return _load_module(ROOT / 'tools' / rel_tool, name)
    except Exception as e:  # noqa: BLE001 — a producer can fail for any import-time reason
        _FAILED_PRODUCERS[name] = f'{type(e).__name__}: {e}'
        return _FailedProducer(name, e)


# REQUIRED: the response models every endpoint declares. If this can't load, fail closed.
_contracts = _load_module(Path(__file__).with_name('contracts.py'), 'dashboard_bff_contracts')
OverviewResponse = _contracts.OverviewResponse
RiskEpFactsResponse = _contracts.RiskEpFactsResponse

# Per-endpoint producers — resilient: one bad import degrades its endpoint, not the service.
_producer = _try_load('emit_intelligence_superiority_metrics.py', 'emit_metrics')
_vdt_producer = _try_load('emit_vdt_metrics.py', 'emit_vdt_metrics')
_gyg_causal_producer = _try_load('emit_gyg_causal.py', 'emit_gyg_causal')
_gyg_locations_producer = _try_load('emit_gyg_locations.py', 'emit_gyg_locations')
_company_financials = _try_load('emit_company_financials.py', 'emit_company_financials')
_studio = _try_load('emit_studio_valuation.py', 'emit_studio_valuation')
_governance_test = _try_load('emit_governance_test.py', 'emit_governance_test')
_risk_ep = _try_load('emit_risk_ep_facts.py', 'emit_risk_ep_facts')
_board_producer = _try_load('emit_intelligence_superiority_board.py', 'emit_is_board')
_board_validator = _try_load('validate_intelligence_superiority_board.py', 'is_board_validator')

if _FAILED_PRODUCERS:
    print(f'[dashboard-bff] WARN {len(_FAILED_PRODUCERS)} producer(s) failed to import and will '
          f'503 on their endpoints; the rest serve: {_FAILED_PRODUCERS}', file=sys.stderr, flush=True)

_SLUG_RE = re.compile(r'[^a-z0-9]+')


def _slug(name: str) -> str:
    return _SLUG_RE.sub('-', name.lower()).strip('-')


def _evidence_for(ref: dict):
    """One evidence_ref -> a web-linkable BoardEvidence, or None (memory-only nodes aren't URLs).

    A ref that carries BOTH `repo` and `memory` (e.g. a repo pointer annotated with a related
    memory-node id) must still resolve to the repo link — `memory` here is supplementary context,
    not a signal to suppress an otherwise-linkable repo reference. Only a ref with no `repo` at
    all (memory-only) is unlinkable."""
    repo = ref.get('repo')
    if not repo:
        return None
    if ref.get('path'):
        href = f'https://github.com/SocioProphet/{repo}/blob/main/{ref["path"]}'
        label = f'{repo}/{ref["path"]}'
    elif ref.get('pr'):
        href = f'https://github.com/SocioProphet/{repo}/pull/{ref["pr"]}'
        label = f'{repo}#{ref["pr"]}'
    else:
        href = f'https://github.com/SocioProphet/{repo}'
        label = repo
    if ref.get('note'):
        label = f'{label} — {ref["note"]}'
    return _contracts.BoardEvidence(label=label, href=href)

app = FastAPI(title='dashboard-bff')

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=['GET', 'POST'],
    allow_headers=['*'],
)

@app.get('/health')
def health() -> dict:
    # 'ok' = the service is up and serving. degraded_producers names any per-endpoint producer
    # that failed to import (those endpoints 503) so the degradation is visible on the liveness
    # surface instead of hidden until someone hits the endpoint. Liveness stays green: a degraded
    # endpoint is not a dead service — that distinction is the whole point of this change.
    return {'service': 'dashboard-bff', 'status': 'ok',
            'degraded_producers': sorted(_FAILED_PRODUCERS)}

@app.get('/v1/overview', response_model=OverviewResponse)
def overview() -> object:
    return OverviewResponse(
        service='dashboard-bff',
        views=['overview', 'deepdive', 'cases', 'intelligence-superiority', 'value-drivers', 'competitive-boards'],
        trace_required=True,
        evidence_required=True,
    )


@app.get('/v1/risk/portfolio-facts', response_model=RiskEpFactsResponse)
def risk_portfolio_facts() -> object:
    """Governed portfolio risk / EP / alternative-inflation facts for the credit-risk viz thesis.
    Risk/EP mirror economic-prophet's model (reproduced_by_us); inflation is reconstructed (vendor
    series proprietary) and flagged, so the UI badges provenance rather than treating all as equal."""
    return RiskEpFactsResponse(**_risk_ep.emit())


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


@app.get('/v1/company/financials')
def company_financials(ticker: str = 'GYG.AX') -> dict:
    """Free, no-key public fundamentals for any exchange:ticker (Value Driver Studio auto-pull).
    Sourced from Yahoo Finance's public quoteSummary via a server-side cookie+crumb handshake —
    global coverage incl. ASX. Returns available=false on failure so the Studio falls back to
    manual entry. Provenance is stamped 'public_market_data'; figures are best-effort, not audited."""
    return _company_financials.fetch(ticker)


@app.get('/v1/valuation/studio/templates')
def studio_templates() -> dict:
    """The industry value-driver-surface templates the Studio offers (reused VDT tensors)."""
    return {'templates': _studio.templates()}


@app.get('/v1/valuation/studio')
def studio_valuation(ticker: str = '', template: str = 'software', ev_baseline: float = 0.0,
                     name: str = '', horizon_years: int = 5, discount_rate: float = 0.09) -> dict:
    """Value Driver Studio — a causal valuation for ANY company. Pass `ticker` (auto-pull free
    public financials for the EV baseline) or `ev_baseline`+`name` (private company), plus an
    industry `template`. Runs the canonical economic-prophet engine; same payload shape as the
    GYG causal walk. Advisory only — not investment advice."""
    return _studio.build_valuation(ticker=ticker or None, template=template,
                                   ev_baseline=ev_baseline or None, name=name or None,
                                   horizon_years=horizon_years, discount_rate=discount_rate)


@app.post('/v1/valuation/studio/recompute')
def studio_recompute(overrides: dict = Body(default={})) -> dict:
    """What-if recompute for the Studio: re-runs the engine with assumption/horizon/discount
    overrides. Body: {ticker?, template, ev_baseline?, name?, horizon_years?, discount_rate?,
    kpi_overrides?}."""
    return _studio.build_valuation(
        ticker=overrides.get('ticker') or None, template=overrides.get('template', 'software'),
        ev_baseline=overrides.get('ev_baseline'), name=overrides.get('name'),
        horizon_years=int(overrides.get('horizon_years', 5)),
        discount_rate=float(overrides.get('discount_rate', 0.09)),
        kpi_overrides=overrides.get('kpi_overrides'))


@app.get('/v1/governance/test')
def governance_test(dataset: str = 'gyg-causal-valuation', action_class: str = 'measurement_render',
                    role: str = 'analyst', requested_level: str = 'L3', evidence: str = '') -> dict:
    """ST012 — ONE reusable governance test, re-runnable against ANY client dataset. Runs the
    deterministic trust-kernel gate (identity → policy → evidence → attestation → revocation → audit)
    and returns a hash-sealed AutonomyAdmissionReceipt (admit/demote/deny) + the step-by-step gate
    trace. Same inputs → same sealed receipt: a repeatable, demonstrable proof of governance, not a
    slide. `evidence` is a comma-separated list of evidence refs."""
    refs = [e.strip() for e in evidence.split(',') if e.strip()]
    return _governance_test.run(dataset=dataset, action_class=action_class, role=role,
                                requested_level=requested_level, evidence_refs=refs)


@app.get('/v1/competitive-boards', response_model=_contracts.CompetitiveBoardsResponse)
def competitive_boards() -> object:
    """Serve the intelligence-superiority FEATURE-BOARD — categorical BEAT/MEET/PARTIAL/GAP verdicts
    against named competitors, per litmus feature. Distinct from /v1/intelligence-superiority above,
    which serves numeric ML benchmark metrics; the two names collide by accident, not by design.

    Built live from tools/emit_intelligence_superiority_board.py, then run through the SAME validator
    the emitter itself gates on (validate_intelligence_superiority_board.validate_board) before being
    served — this route can never ship a board the emitter's own honesty gate would reject. Relative-only
    scoring model: every cell is the estate's claim about its standing against ONE competitor on ONE
    feature, so there is no separate 'estate column' — see BoardCellView."""
    board = _board_producer.build_board()
    verdict = _board_validator.validate_board(board)
    if not verdict.valid:
        raise HTTPException(status_code=500, detail={
            'error': 'intelligence-superiority board failed its own validator',
            'rejections': verdict.rejections,
        })

    categories = []
    for cat in board['categories']:
        competitors = [_contracts.BoardCompetitor(id=_slug(c), name=c) for c in cat['competitors']]
        features = [
            _contracts.LitmusFeatureView(id=f['feature_id'], name=f['name'], definition=f['definition'])
            for f in cat['litmus_features']
        ]
        cells = []
        for s in cat['scores']:
            evidence = None
            for ref in (s.get('evidence_ref') or []):
                evidence = _evidence_for(ref)
                if evidence:
                    break
            cells.append(_contracts.BoardCellView(
                feature_id=s['feature_id'],
                competitor_id=_slug(s['competitor']),
                rank=s['verdict'],
                evidence=evidence,
                maturity=s.get('maturity'),
                basis='self-assessed' if s.get('assessment_basis') == 'self_assessed' else 'externally-certified',
                note=s.get('rationale'),
                provisional=bool(s.get('provisional', False)),
            ))
        categories.append(_contracts.CategoryBoardView(
            id=cat['category_id'], name=cat['name'], description=cat['description'],
            competitors=competitors, features=features, cells=cells,
        ))

    return _contracts.CompetitiveBoardsResponse(
        service='dashboard-bff',
        version=board.get('spec_version', '1.0.0'),
        generated_at=board['generated_ts'],
        estate_label='SocioProphet Estate',
        categories=categories,
        disclaimer=board.get('notes', ''),
    )


import json as _json


def _load_round_fixtures() -> list[dict]:
    examples = ROOT / 'schemas' / 'eval' / 'examples'
    rounds = []
    for p in sorted(examples.glob('leaderboard-round.*.example.json')):
        try:
            rounds.append(_json.loads(p.read_text(encoding='utf-8')))
        except Exception:  # skip malformed fixture files — CI will surface them via the validate workflow
            pass
    return rounds


@app.get('/v1/rounds')
def leaderboard_rounds(division: str | None = None) -> dict:
    """Serve published leaderboard rounds (schemas/eval/leaderboard-round.schema.json, #1304).

    Returns all published rounds split by division: CLOSED (strict ranked, comparable)
    and OPEN (tiered, NOT comparable to CLOSED — different methods). Only rounds whose
    fixture data is well-formed are served.

    Query ?division=CLOSED or ?division=OPEN to filter. Omit for all rounds.

    Non-claim: serves static fixtures from schemas/eval/examples/. Does not execute
    evaluations, modify scoring, or assert production readiness of any entry.
    """
    all_rounds = _load_round_fixtures()
    if division:
        all_rounds = [r for r in all_rounds if r.get('division') == division.upper()]

    closed = [r for r in all_rounds if r.get('division') == 'CLOSED']
    open_ = [r for r in all_rounds if r.get('division') == 'OPEN']

    return {
        'rounds': all_rounds,
        'closed_count': len(closed),
        'open_count': len(open_),
        'non_comparable_warning': (
            'OPEN rounds use novel methods and are NOT directly comparable to CLOSED rounds. '
            'Do not render a head-to-head bar between OPEN and CLOSED divisions.'
        ),
        'source': 'fixture',
        'non_claims': [
            'Fixture-only. Does not reflect a live scoring database.',
            'Does not execute new evaluations or modify scores.',
            'OPEN rounds are not certified for production use.',
        ],
    }
