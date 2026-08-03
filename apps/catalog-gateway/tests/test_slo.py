"""Catalog operational-plane SLO-gate tests (the Assay verdict over a readout)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402
from app import slo  # noqa: E402

client = TestClient(app)


def _readout(*, hit_rate, resolve_total, coverage, distinct_assets, cataloged, cold):
    """Synthesize just the fields slo.evaluate() reads."""
    return {
        "readout_id": "ro_test",
        "resolve": {"total": resolve_total, "hits": 0, "misses": 0,
                    "hit_rate": hit_rate, "by_kind": {}},
        "dcat": {"emissions": 0, "distinct_assets": distinct_assets,
                 "coverage_of_resolved_assets": coverage},
        "sources": {"cataloged": cataloged, "read_in_window": 0, "cold": cold},
        "window": {"events_scanned": 0, "first_event_at": None, "last_event_at": None},
    }


def test_all_green_is_ok():
    ro = _readout(hit_rate=0.95, resolve_total=40, coverage=0.9, distinct_assets=40,
                  cataloged=40, cold=[f"s{i}" for i in range(4)])  # cold ratio 0.1
    r = slo.evaluate(ro)
    assert r["verdict"] == "ok"
    assert {o["name"]: o["verdict"] for o in r["objectives"]} == {
        "resolve_hit_rate": "ok", "dcat_coverage": "ok", "cold_source_ratio": "ok"}


def test_worst_objective_wins_meet_min():
    # hit_rate ok, coverage sad, cold_ratio bad → overall bad (min semantics)
    ro = _readout(hit_rate=0.95, resolve_total=40, coverage=0.6, distinct_assets=40,
                  cataloged=40, cold=[f"s{i}" for i in range(30)])  # cold ratio 0.75 → bad
    r = slo.evaluate(ro)
    verdicts = {o["name"]: o["verdict"] for o in r["objectives"]}
    assert verdicts["resolve_hit_rate"] == "ok"
    assert verdicts["dcat_coverage"] == "sad"
    assert verdicts["cold_source_ratio"] == "bad"
    assert r["verdict"] == "bad"  # worst wins, no averaging


def test_sad_when_worst_is_sad():
    ro = _readout(hit_rate=0.75, resolve_total=40, coverage=0.9, distinct_assets=40,
                  cataloged=40, cold=["s0"])  # cold ratio ~0.025 ok, hit_rate 0.75 sad
    r = slo.evaluate(ro)
    assert r["verdict"] == "sad"


def test_insufficient_data_below_min_n():
    # only 10 resolves and 5 assets → hit_rate + coverage objectives are insufficient;
    # cataloged=5 → cold_ratio also insufficient → overall insufficient_data.
    ro = _readout(hit_rate=1.0, resolve_total=10, coverage=1.0, distinct_assets=5,
                  cataloged=5, cold=[])
    r = slo.evaluate(ro)
    assert r["verdict"] == "insufficient_data"
    assert all(o["verdict"] == "insufficient_data" for o in r["objectives"])
    assert any("n=10 < min_n=30" in o["note"] for o in r["objectives"])


def test_insufficient_does_not_drag_the_graded_verdict():
    # hit_rate graded ok (n=40); coverage insufficient (n=5) → overall follows the
    # graded objective (ok), the insufficient one neither passes nor fails.
    ro = _readout(hit_rate=0.95, resolve_total=40, coverage=1.0, distinct_assets=5,
                  cataloged=40, cold=[])
    r = slo.evaluate(ro)
    assert r["verdict"] == "ok"
    cov = next(o for o in r["objectives"] if o["name"] == "dcat_coverage")
    assert cov["verdict"] == "insufficient_data"


def test_none_value_is_insufficient():
    ro = _readout(hit_rate=None, resolve_total=0, coverage=None, distinct_assets=0,
                  cataloged=0, cold=[])
    r = slo.evaluate(ro)
    assert r["verdict"] == "insufficient_data"


def test_low_direction_boundary():
    # cold ratio exactly at ok threshold (0.20) → ok (<=); just above → sad
    ok = slo.evaluate(_readout(hit_rate=0.95, resolve_total=40, coverage=0.9,
                               distinct_assets=40, cataloged=100,
                               cold=[f"s{i}" for i in range(20)]))  # 0.20
    assert next(o for o in ok["objectives"] if o["name"] == "cold_source_ratio")["verdict"] == "ok"
    sad = slo.evaluate(_readout(hit_rate=0.95, resolve_total=40, coverage=0.9,
                                distinct_assets=40, cataloged=100,
                                cold=[f"s{i}" for i in range(21)]))  # 0.21
    assert next(o for o in sad["objectives"] if o["name"] == "cold_source_ratio")["verdict"] == "sad"


def _drive_events(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("CATALOG_OPS_CAPTURE", "true")
    d = tmp_path / "prophet-platform" / "catalog" / "asset"
    d.mkdir(parents=True, exist_ok=True)
    (d / "a1.json").write_text(json.dumps({"asset_id": "a1", "asset_kind": "dataset",
                                            "tenant_id": "t", "distribution_class": "public_derived",
                                            "created_at": "2026-08-01T00:00:00Z",
                                            "updated_at": "2026-08-01T00:00:00Z"}), encoding="utf-8")
    assert client.get("/v1/catalog/asset/a1").status_code == 200


def test_emit_crystallizes_slo_event(monkeypatch, tmp_path):
    _drive_events(monkeypatch, tmp_path)
    doc, event_id = slo.emit_slo()
    assert event_id is not None
    ev = tmp_path / "prophet-platform" / "events" / "catalog-gateway"
    written = [json.loads(p.read_text()) for p in ev.glob("*.event.json")]
    slos = [e for e in written if e["event_type"] == "crystal-atlas.catalog.ops.slo.v0"]
    assert len(slos) == 1 and slos[0]["event"]["slo_id"] == doc["slo_id"]


def test_route_get_and_post(monkeypatch, tmp_path):
    _drive_events(monkeypatch, tmp_path)
    g = client.get("/v1/catalog/ops/slo")
    assert g.status_code == 200
    # 1 resolve → below min_n → insufficient_data, not a false pass/fail
    assert g.json()["verdict"] == "insufficient_data"
    p = client.post("/v1/catalog/ops/slo")
    assert p.status_code == 200 and p.json()["event_id"] is not None
