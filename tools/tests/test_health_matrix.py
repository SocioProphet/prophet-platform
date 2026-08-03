"""RepoHealthMatrix aggregator — pure classification + schema conformance, from a
signals fixture (offline)."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import build_health_matrix as hm  # noqa: E402

FIX = json.loads((Path(__file__).parent / "fixtures" / "health_signals.json").read_text())
SCHEMA = json.loads((ROOT / "contracts" / "RepoHealthMatrix.v0.1.json").read_text())


def _row(matrix, name):
    return next(r for r in matrix["rows"] if r["resource"].endswith(name))


def test_classification():
    m = hm.build_matrix(FIX["signals"], FIX["scope"])
    healthy = _row(m, "healthy-svc")
    assert healthy["ci_health"] == "ok" and healthy["security_posture"] == "ok"
    assert healthy["agent_finding"] == "healthy" and healthy["risk_tier"] == "low"

    ci = _row(m, "ci-broken")
    assert ci["ci_health"] == "fail" and ci["risk_tier"] == "medium"
    assert "CI failing" in ci["agent_finding"]

    vuln = _row(m, "vuln-svc")
    assert vuln["security_posture"] == "fail" and vuln["risk_tier"] == "high"
    assert "security" in vuln["agent_finding"]

    orphan = _row(m, "orphan-lib")
    assert orphan["risk_tier"] == "medium"  # no owner
    assert orphan["last_activity"] == "fail" and orphan["docs_freshness"] == "fail"
    assert "no maintainer" in orphan["agent_finding"]


def test_matrix_conforms_to_schema():
    m = hm.build_matrix(FIX["signals"], FIX["scope"])
    try:
        import jsonschema
    except ImportError:
        return
    jsonschema.validate(m, SCHEMA)
    assert m["rows"] == sorted(m["rows"], key=lambda r: r["resource"])  # stable order


def test_rows_cover_all_dimensions():
    m = hm.build_matrix(FIX["signals"], FIX["scope"])
    for r in m["rows"]:
        for dim in hm.DIMENSIONS:
            assert r[dim] in ("ok", "warn", "fail", "unknown")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
