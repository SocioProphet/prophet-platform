"""Boot resilience: one broken producer must not crashloop the whole dashboard-bff.

The 2026-08-04 incident: dashboard-bff eagerly imported ~11 tools/emit_*.py producers at boot;
emit_risk_ep_facts.py imports a vendored framework (open_ep_framework) absent from the prod
image, so the WHOLE service crashlooped (120+ restarts) — every endpoint down because one
endpoint's producer couldn't import. The fix degrades a failed producer to a loud per-endpoint
503 and keeps the service up. These pin it both ways.
"""
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main  # noqa: E402

client = TestClient(main.app)


def test_boots_and_health_reports_producer_status():
    r = client.get('/health')
    assert r.status_code == 200
    body = r.json()
    assert body['status'] == 'ok'
    # degradation is VISIBLE on the liveness surface, not hidden until an endpoint is hit
    assert isinstance(body['degraded_producers'], list)


def test_overview_serves():
    # proves the app booted and a non-producer endpoint serves
    assert client.get('/v1/overview').status_code == 200


def test_failed_producer_sentinel_raises_503_naming_the_error():
    fp = main._FailedProducer('emit_risk_ep_facts', ImportError("No module named 'open_ep_framework'"))
    with pytest.raises(HTTPException) as ei:
        fp.emit()
    assert ei.value.status_code == 503
    assert 'emit_risk_ep_facts' in ei.value.detail
    assert 'open_ep_framework' in ei.value.detail


def test_try_load_missing_tool_degrades_instead_of_crashing():
    main._FAILED_PRODUCERS.pop('ghost_producer', None)
    mod = main._try_load('definitely_missing_tool_qux.py', 'ghost_producer')
    assert isinstance(mod, main._FailedProducer)          # boot survives a missing producer
    assert 'ghost_producer' in main._FAILED_PRODUCERS      # recorded → /health + startup log


def test_incident_repro_missing_producer_503s_its_endpoint_others_stay_up(monkeypatch):
    # Reproduce the exact incident: the risk-EP producer can't import in the prod image.
    monkeypatch.setattr(main, '_risk_ep', main._FailedProducer(
        'emit_risk_ep_facts', ImportError("No module named 'open_ep_framework'")))
    # its endpoint fails LOUDLY, naming the missing dependency...
    r = client.get('/v1/risk/portfolio-facts')
    assert r.status_code == 503
    assert 'open_ep_framework' in r.json()['detail']
    # ...while an unrelated endpoint keeps serving — the service is degraded, NOT down.
    assert client.get('/v1/overview').status_code == 200
