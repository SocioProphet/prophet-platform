"""Teeth for the governed risk/EP/inflation producer + the dashboard-bff endpoint."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


emit = _load("emit_risk_ep_facts").emit


def _val(out, name):
    return next(f["value"] for f in out["facts"] if f["name"] == name)


def test_expected_loss_is_pd_lgd_ead():
    out = emit({"pd": 0.02, "lgd": 0.45, "ead": 100.0, "rho": 0.15, "confidence": 0.999})
    assert abs(_val(out, "expected_loss") - 0.02 * 0.45 * 100.0) < 1e-9


def test_economic_capital_positive_and_var_exceeds_el():
    out = emit()
    assert _val(out, "credit_var") > _val(out, "expected_loss")
    assert _val(out, "economic_capital") > 0


def test_recovery_wedge_negative_market_below_planning():
    out = emit()
    assert _val(out, "recovery_market_rr_q") < _val(out, "recovery_planning_rr_p")
    assert _val(out, "recovery_wedge") < 0


def test_shadowstats_above_official_and_lowers_real_rate():
    out = emit()
    assert _val(out, "shadowstats_inflation") > _val(out, "official_cpi_inflation")
    assert _val(out, "real_rate_shadowstats") < _val(out, "real_rate_official")


def test_provenance_flags_reconstructed_vs_reproduced():
    out = emit()
    infl = {f["name"]: f for f in out["facts"] if "inflation" in f["name"] and f["name"] != "official_cpi_inflation"}
    assert all(f["reconstructed"] and not f["reproduced_by_us"] for f in infl.values())
    risk = next(f for f in out["facts"] if f["name"] == "economic_capital")
    assert risk["reproduced_by_us"] and not risk["reconstructed"]
    assert out["provenance"]["governed"] is True


def test_endpoint_returns_governed_facts():
    testclient = pytest.importorskip("fastapi.testclient")
    spec = importlib.util.spec_from_file_location("bff_main", ROOT / "apps" / "dashboard-bff" / "main.py")
    main = importlib.util.module_from_spec(spec); spec.loader.exec_module(main)
    client = testclient.TestClient(main.app)
    r = client.get("/v1/risk/portfolio-facts")
    assert r.status_code == 200
    body = r.json()
    assert body["provenance"]["governed"] is True
    assert any(f["name"] == "expected_loss" for f in body["facts"])
