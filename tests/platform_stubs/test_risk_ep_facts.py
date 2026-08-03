"""Teeth + DOGFOOD proof: the bff producer computes its numbers from the vendored
open_ep_framework (single source of truth), not hand-mirrored formulas."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "third_party"))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


emit = _load("emit_risk_ep_facts").emit


def _val(out, name):
    return next(f["value"] for f in out["facts"] if f["name"] == name)


def test_dogfood_numbers_come_from_the_vendored_framework():
    # the producer's numbers must EQUAL the vendored functions called directly — one source of truth
    from open_ep_framework import expected_loss, regulatory_capital
    from open_ep_framework.domain import ExpectedLossInputs
    p = {"pd": 0.02, "lgd": 0.45, "ead": 100.0}
    out = emit(p)
    assert abs(_val(out, "expected_loss")
               - expected_loss.expected_loss_amount(ExpectedLossInputs(0.02, 0.45, 100.0))) < 1e-9
    assert abs(_val(out, "regulatory_capital_credit")
               - regulatory_capital.irb_regulatory_capital(0.02, 0.45, 100.0)["regulatory_capital"]) < 1e-6
    assert out["provenance"]["dogfood"] is True
    assert "vendored" in out["provenance"]["engine"]


def test_irb_and_oprisk_facts_present_and_sane():
    out = emit()
    assert 0.12 <= _val(out, "irb_correlation") <= 0.24
    assert _val(out, "regulatory_capital_credit") > 0
    assert _val(out, "oprisk_capital_ama") > 0
    assert _val(out, "regulatory_capital_total") > _val(out, "regulatory_capital_credit")


def test_reg_vs_economic_comparison_in_detail():
    out = emit()
    cc = out["detail"]["capital_comparison"]
    assert cc["regulatory"]["total"] > 0 and cc["economic"]["total"] > 0
    assert cc["divergence"]["binding_constraint"] in ("economic", "regulatory")


def test_marketing_infotheory_for_our_companies():
    out = emit()
    mk = out["detail"]["marketing"]
    assert any(c["company"] == "SocioProphet" for c in mk)
    for co in mk:
        shares = [ch["info_share"] for ch in co["channels"].values()]
        assert abs(sum(shares) - 1.0) < 1e-6          # info-gain attribution sums to 1
        assert co["mutual_information_bits"] >= 0
        assert co["blended_cac"] > 0


def test_inflation_reconstructed_flagged():
    out = emit()
    ss = next(f for f in out["facts"] if f["name"] == "shadowstats_inflation")
    assert ss["reconstructed"] and not ss["reproduced_by_us"]
    assert _val(out, "real_rate_shadowstats") < _val(out, "real_rate_official")


def test_endpoint_returns_governed_facts():
    testclient = pytest.importorskip("fastapi.testclient")
    spec = importlib.util.spec_from_file_location("bff_main", ROOT / "apps" / "dashboard-bff" / "main.py")
    main = importlib.util.module_from_spec(spec); spec.loader.exec_module(main)
    client = testclient.TestClient(main.app)
    r = client.get("/v1/risk/portfolio-facts")
    assert r.status_code == 200
    body = r.json()
    assert body["provenance"]["dogfood"] is True
    assert body["detail"]["marketing"]
