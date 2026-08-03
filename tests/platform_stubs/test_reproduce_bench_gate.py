"""Teeth for the unified reproduce path + fail-closed tolerance gate.

A control that never fires is suspect, so the gate is proven BOTH ways:

  POSITIVE — a within-tolerance re-run PASSES (deterministic exact; bounded within
             epsilon), and the gate CLI exits 0.
  NEGATIVE — an injected drift beyond epsilon makes the gate FAIL, and the gate CLI
             exits non-zero (fail-closed).

Plus: every emitted repro-ledger-entry validates against the real schema, the spine
is content-addressed + hash-chained (tamper-evident), and round_id/version are
stamped on every record.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas" / "eval"


def _rb():
    path = ROOT / "tools" / "reproduce_bench.py"
    spec = importlib.util.spec_from_file_location("reproduce_bench", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _det_record():
    return _rb().load_record(ROOT / "contracts" / "reproduce" / "isota" / "opus-class-r1.run.json")


def _bnd_record():
    return _rb().load_record(ROOT / "contracts" / "reproduce" / "isota" / "sampled-headline-r1.run.json")


# ---------------------------------------------------------------- POSITIVE ----
def test_positive_deterministic_rerun_reproduces_exactly_and_passes():
    rb = _rb()
    rec = _det_record()
    observed = rb.observe(rec)                 # real in-process re-run of the composite
    passed, detail = rb.reproduce_gate(rec, observed)
    assert passed is True
    assert detail["delta"] == 0.0              # exact
    assert detail["rule"] == "exact"
    assert observed == rec["headline_value"]


def test_positive_bounded_within_epsilon_passes():
    rb = _rb()
    rec = _bnd_record()
    observed = rb.observe(rec)                 # pinned seed -> reproduces
    passed, detail = rb.reproduce_gate(rec, observed)
    assert passed is True
    assert detail["delta"] <= rec["epsilon"]
    assert detail["rule"] == "within_epsilon"


def test_positive_bounded_at_epsilon_boundary_passes():
    rb = _rb()
    rec = _bnd_record()
    observed = rec["headline_value"] + rec["epsilon"]   # exactly at tolerance
    passed, detail = rb.reproduce_gate(rec, observed)
    assert passed is True
    assert detail["delta"] == pytest.approx(rec["epsilon"])


# ---------------------------------------------------------------- NEGATIVE ----
def test_negative_deterministic_any_drift_fails():
    rb = _rb()
    rec = _det_record()
    observed = rec["headline_value"] + 0.01    # tiny drift, but arm is exact
    passed, detail = rb.reproduce_gate(rec, observed)
    assert passed is False
    assert detail["rule"] == "exact"


def test_negative_bounded_drift_beyond_epsilon_fails():
    rb = _rb()
    rec = _bnd_record()
    observed = rec["headline_value"] + rec["epsilon"] * 2 + 1e-6  # beyond tolerance
    passed, detail = rb.reproduce_gate(rec, observed)
    assert passed is False
    assert detail["delta"] > rec["epsilon"]


def test_negative_unknown_determinism_fails_closed():
    rb = _rb()
    rec = _bnd_record()
    rec = {**rec, "determinism": "wat"}
    passed, detail = rb.reproduce_gate(rec, rec["headline_value"])
    assert passed is False                     # never a silent pass
    assert detail["rule"] == "unknown_determinism_fail_closed"


# --------------------------------------------------- CLI exit codes (teeth) ---
def test_cli_gate_passes_exit_zero_on_within_tolerance():
    rb = _rb()
    rc = rb.main(["--bench", "isota", "--run", "opus-class-r1", "--gate"])
    assert rc == 0


def test_cli_gate_fails_exit_nonzero_on_injected_drift():
    rb = _rb()
    rec = _det_record()
    drifted = rec["headline_value"] + 5.0
    rc = rb.main(["--bench", "isota", "--run", "opus-class-r1", "--gate",
                  "--inject-observed", str(drifted)])
    assert rc == 1                             # FAIL CLOSED


# ------------------------------------------------- ledger + chain + schema ----
def test_repro_ledger_entry_validates_and_is_chained(tmp_path):
    rb = _rb()
    rec = _det_record()
    ledger = tmp_path / "repro-ledger.jsonl"
    # emit two entries; the second must chain to the first.
    s1 = rb.emit_ledger_entry(rec, rec["headline_value"], True,
                              rb.reproduce_gate(rec, rec["headline_value"])[1], ledger=ledger)
    s2 = rb.emit_ledger_entry(rec, rec["headline_value"], True,
                              rb.reproduce_gate(rec, rec["headline_value"])[1], ledger=ledger)
    schema = json.loads((SCHEMA_DIR / "repro-ledger-entry.schema.json").read_text())
    jsonschema.validate(s1["entry"], schema)
    jsonschema.validate(s2["entry"], schema)
    assert s1["prev_entry_digest"] == ""                       # genesis
    assert s2["prev_entry_digest"] == s1["entry_digest"]       # chained
    assert s1["round_id"] == rec["round_id"] and s1["version"] == rec["version"]  # stamped
    assert rb.verify_ledger(ledger) is True


def test_ledger_tamper_is_detected(tmp_path):
    rb = _rb()
    rec = _det_record()
    ledger = tmp_path / "repro-ledger.jsonl"
    rb.emit_ledger_entry(rec, rec["headline_value"], True,
                         rb.reproduce_gate(rec, rec["headline_value"])[1], ledger=ledger)
    assert rb.verify_ledger(ledger) is True
    # flip the recorded outcome without recomputing the digest -> chain breaks.
    line = json.loads(ledger.read_text().splitlines()[0])
    line["reproduce_outcome"]["observed"] = 999.0
    ledger.write_text(json.dumps(line, sort_keys=True) + "\n")
    assert rb.verify_ledger(ledger) is False
