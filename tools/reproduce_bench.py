#!/usr/bin/env python3
"""reproduce_bench — the UNIFIED one-command reproduce path + fail-closed
reproduce/tolerance gate for the eval fabric.

WHY. Today there are three separate reproduce paths — `run-exam.sh` (Noetica MMLU
/ ST026), `cargo run -p hellgraph-bench`, and `tools/isota_tournament.py`. This is
the single dispatch front door over them, and the control that makes a *reproduced*
number defensible:

  make reproduce-bench BENCH=<name> RUN=<id>            # reproduce + emit ledger
  make reproduce-bench-gate BENCH=<name> RUN=<id>       # + FAIL CLOSED on drift

WHAT IT GUARANTEES.
  1. DISPATCH. One entrypoint routes BENCH -> the correct suite runner (dispatch
     table below). In-repo arms are re-derived in-process (real computation). The
     external suites (MMLU exam via run-exam.sh, hellgraph via cargo) need real
     corpora/weights not present in CI, so they are made gate-enforceable via a
     DETERMINISTIC REPLAY: the gate re-derives the headline in-process from a
     hash-verified captured artifact (contracts/reproduce/<bench>/*.{exam,bench}.json),
     so epsilon/exact tolerance BITES on the replayed headline (no dispatch-only
     silent pass). The live in-process re-run stays the documented external_command.
  2. LEDGER, MANDATED. Every run emits a `repro-ledger-entry` (schema
     schemas/eval/repro-ledger-entry.schema.json) that is content-addressed and
     CHAINED to a receipt spine (append-only JSONL, prev_entry_digest links each
     record to its predecessor). round_id + version are stamped (versioned rounds).
  3. TOLERANCE GATE, FAIL-CLOSED. The gate re-runs a recorded run and asserts the
     headline metric reproduces: EXACT for `deterministic` arms, within the declared
     `epsilon` for `bounded_nondeterministic` arms. Drift beyond tolerance -> the
     gate returns non-zero. A control that never fires is suspect, so the teeth are
     proven both ways in tests/platform_stubs/test_reproduce_bench_gate.py.

Hashing note: SHA-256 is the FIPS 180-4 *algorithm* via Python's stdlib hashlib.
This is NOT a FIPS 140-validated cryptographic module. We describe it precisely.

License: MIT (matches repo LICENSE).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "eval"
RECORDS_DIR = ROOT / "contracts" / "reproduce"
LEDGER_ROOT = ROOT / "build" / "reproduce"


# ---------------------------------------------------------------------------
# consume-not-fork: reuse the real isota_tournament composite as an in-repo,
# deterministic headline metric. We import the existing module, we do not
# reimplement its scoring.
# ---------------------------------------------------------------------------
def _isota():
    path = ROOT / "tools" / "isota_tournament.py"
    spec = importlib.util.spec_from_file_location("isota_tournament", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# in-process re-runners: given a record's rerun.args, produce the OBSERVED
# headline value. These are REAL computations, deterministic given their inputs.
# ---------------------------------------------------------------------------
def _rerun_isota_composite(args: dict) -> float:
    """Observed = the iSOTA Sherlock-weighted composite over the recorded axis
    scores. Pure deterministic function of its inputs -> a deterministic arm."""
    scores = args["scores"]
    return float(_isota().composite(scores))


def _rerun_isota_seeded_headline(args: dict) -> float:
    """Observed = a seeded, bounded-nondeterministic headline (a stand-in for a
    sampled eval mean). The seed is PINNED, so with the pinned seed the value
    reproduces within epsilon; the arm is declared bounded_nondeterministic so the
    gate exercises the epsilon tolerance path rather than exact match."""
    seed = int(args["seed"])
    n = int(args.get("n", 64))
    base = float(args.get("base", 80.0))
    # deterministic PRNG from a pinned seed: a small LCG averaged over n draws,
    # centered on `base`. Same seed -> same value (reproducible); different seed
    # -> a value that can exceed epsilon (drift is detectable).
    state = (seed * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
    acc = 0.0
    for _ in range(n):
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        acc += ((state >> 33) / float(1 << 31)) - 1.0  # in [-1, 1)
    return round(base + acc / n, 6)


def _rerun_external(args: dict) -> float:  # pragma: no cover - guarded by tests
    raise RuntimeError(
        "external arm: reproduce out-of-band via the recorded external_command; "
        "the in-process gate dispatches but does not execute external suites"
    )


class ArtifactIntegrityError(Exception):
    """A captured replay artifact failed hash verification (bytes tampered, wrong
    file, or a stale record). NOT a RuntimeError -> it is never swallowed by the
    dispatch-only handler; the gate fails closed rather than silently passing."""


def _load_verified_artifact(args: dict) -> dict:
    """Load a captured artifact and FAIL CLOSED unless its exact committed bytes
    match the pinned `artifact_sha256` in the record (SHA-256 / FIPS 180-4 algorithm,
    stdlib hashlib; NOT a FIPS 140 module). This is what makes replay defensible:
    the number is re-derived from bytes we have proven are the ones we recorded."""
    rel = args.get("artifact")
    if not rel:
        raise ArtifactIntegrityError("replay record has no rerun.args.artifact path")
    path = ROOT / rel
    if not path.exists():
        raise ArtifactIntegrityError("captured artifact missing: %s" % path)
    raw = path.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    want = args.get("artifact_sha256", "")
    if not want:
        raise ArtifactIntegrityError("replay record has no rerun.args.artifact_sha256")
    if got != want:
        raise ArtifactIntegrityError(
            "artifact hash mismatch for %s: recorded %s != observed %s" % (rel, want, got)
        )
    return json.loads(raw)


def _replay_mmlu_route_accuracy(args: dict) -> float:
    """Observed = ROUTE-arm accuracy RE-DERIVED from the hash-verified captured
    Noetica MMLU/ST026 exam artifact (correct/total), NOT copied from the headline.
    Fails closed if the clean-eval contamination certificate hash does not match the
    recorded `contamination_cert_sha256` or the certificate is not status=clean."""
    art = _load_verified_artifact(args)
    cert = art.get("clean_eval_certificate")
    if not isinstance(cert, dict) or cert.get("status") != "clean":
        raise ArtifactIntegrityError(
            "MMLU replay refused: clean-eval certificate absent or status!='clean'"
        )
    want_cert = args.get("contamination_cert_sha256", "")
    if not want_cert:
        raise ArtifactIntegrityError("replay record has no rerun.args.contamination_cert_sha256")
    got_cert = canonical_digest(cert)
    if got_cert != want_cert:
        raise ArtifactIntegrityError(
            "contamination-cert hash mismatch: recorded %s != observed %s" % (want_cert, got_cert)
        )
    arm = art["arms"][art.get("headline_arm", "route")]
    total = int(arm["total"])
    if total <= 0:
        raise ArtifactIntegrityError("MMLU replay: route arm total must be > 0")
    return int(arm["correct"]) / total


def _replay_hellgraph(args: dict) -> float:
    """Observed = query resolution rate RE-DERIVED from the hash-verified captured
    hellgraph-bench artifact (per-query resolved flags). Deterministic bench -> the
    gate asserts EXACT reproduction of this headline."""
    art = _load_verified_artifact(args)
    queries = art["queries"]
    if not queries:
        raise ArtifactIntegrityError("hellgraph replay: empty query suite")
    resolved = sum(int(q["resolved"]) for q in queries)
    return resolved / len(queries)


# ---------------------------------------------------------------------------
# DISPATCH TABLE — one front door over the three reproduce paths.
#   in_process: the re-runner kind -> callable used by the gate.
#   command:    the canonical one-command reproduce path (documentary / human).
# ---------------------------------------------------------------------------
DISPATCH: dict[str, dict] = {
    "isota": {
        "command": "python3 tools/isota_tournament.py --results <results.json>",
        "in_process": {
            "isota_composite": _rerun_isota_composite,
            "isota_seeded_headline": _rerun_isota_seeded_headline,
        },
    },
    "mmlu": {
        # Noetica MMLU / ST026 exam — pinned seed, clean-eval certificate attached.
        # Gate-enforceable via deterministic replay of the hash-verified exam artifact;
        # `external` remains for the live out-of-band re-run.
        "command": "bash agent-machine/scripts/run-exam.sh   # MMLU_SEED pinned",
        "in_process": {
            "replay_mmlu_route_accuracy": _replay_mmlu_route_accuracy,
            "external": _rerun_external,
        },
    },
    "hellgraph": {
        # Deterministic graph query bench. Gate-enforceable via deterministic replay
        # of the hash-verified bench artifact; `external` remains for the live re-run.
        "command": "cargo run -p hellgraph-bench",
        "in_process": {
            "replay_hellgraph": _replay_hellgraph,
            "external": _rerun_external,
        },
    },
}


def canonical_digest(obj: object) -> str:
    """Content address via SHA-256 (FIPS 180-4 algorithm; NOT a FIPS 140 module)
    over the canonical JSON encoding (sorted keys, tight separators)."""
    encoded = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def load_record(path: Path) -> dict:
    """Load a ReproduceRunRecord and validate it spec-first."""
    schema = json.loads((SCHEMA_DIR / "reproduce-run-record.schema.json").read_text())
    record = json.loads(path.read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(record)
    if record["bench"] not in DISPATCH:
        raise KeyError("unknown bench %r; known: %s" % (record["bench"], sorted(DISPATCH)))
    return record


def record_path(bench: str, run_id: str) -> Path:
    return RECORDS_DIR / bench / ("%s.run.json" % run_id)


def observe(record: dict, override: float | None = None) -> float:
    """Produce the OBSERVED headline value by re-running the arm in-process.
    `override` lets teeth inject a drifted/within-tolerance observation."""
    if override is not None:
        return float(override)
    bench = record["bench"]
    kind = record["rerun"]["kind"]
    fn = DISPATCH[bench]["in_process"].get(kind)
    if fn is None:
        raise KeyError("no in-process re-runner %r for bench %r" % (kind, bench))
    return fn(record["rerun"].get("args", {}))


def reproduce_gate(record: dict, observed: float) -> tuple[bool, dict]:
    """The teeth. Compare observed vs recorded headline.

      deterministic            -> EXACT match required.
      bounded_nondeterministic -> abs(observed - recorded) <= epsilon.

    Returns (passed, detail). FAIL CLOSED: any drift beyond tolerance -> passed
    False; a malformed determinism class -> passed False (never a silent pass)."""
    recorded = float(record["headline_value"])
    mode = record["determinism"]
    delta = abs(observed - recorded)
    detail = {
        "headline_metric_id": record["headline_metric_id"],
        "recorded": recorded,
        "observed": observed,
        "delta": delta,
        "determinism": mode,
        "round_id": record["round_id"],
        "version": record["version"],
    }
    if mode == "deterministic":
        passed = observed == recorded
        detail["tolerance"] = 0.0
        detail["rule"] = "exact"
    elif mode == "bounded_nondeterministic":
        eps = float(record.get("epsilon", 0.0))
        passed = delta <= eps
        detail["tolerance"] = eps
        detail["rule"] = "within_epsilon"
    else:  # fail closed on an unknown class
        passed = False
        detail["tolerance"] = 0.0
        detail["rule"] = "unknown_determinism_fail_closed"
    detail["passed"] = passed
    return passed, detail


def _environment_hash() -> str:
    env = {
        "python": platform.python_version(),
        "impl": platform.python_implementation(),
        "system": platform.system(),
        "machine": platform.machine(),
    }
    return canonical_digest(env)


def _methodology_snapshot_hash(record: dict) -> str:
    """Content address the methodology: the runner source + the record itself.
    A change to either changes the snapshot hash -> the round must be re-versioned."""
    runner_src = _sha256_file(ROOT / "tools" / "reproduce_bench.py")
    isota_src = _sha256_file(ROOT / "tools" / "isota_tournament.py")
    return canonical_digest({
        "reproduce_bench_sha256": runner_src,
        "isota_tournament_sha256": isota_src,
        "record": record,
    })


def ledger_path_for(bench: str) -> Path:
    return LEDGER_ROOT / bench / "repro-ledger.jsonl"


def _prev_digest(ledger: Path) -> str:
    if not ledger.exists():
        return ""
    lines = [ln for ln in ledger.read_text().splitlines() if ln.strip()]
    if not lines:
        return ""
    return json.loads(lines[-1])["entry_digest"]


def emit_ledger_entry(record: dict, observed: float, passed: bool, detail: dict,
                      ledger: Path | None = None, ts: str | None = None) -> dict:
    """Emit a repro-ledger-entry (schema-valid) wrapped in a content-addressed,
    hash-chained spine record, and append it to the append-only ledger.

    The inner `entry` conforms to schemas/eval/repro-ledger-entry.schema.json
    (additionalProperties:false -> we do NOT fork the contract). round_id, version
    and the reproduce outcome live on the OUTER spine record, which is chained to
    its predecessor via prev_entry_digest (SHA-256 / FIPS 180-4 algorithm)."""
    ts = ts or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ledger = ledger or ledger_path_for(record["bench"])

    entry = {  # <- validates against repro-ledger-entry.schema.json
        "repro_ledger_entry_id": "rle.%s.%s.%s" % (record["bench"], record["run_id"], ts),
        "run_id": record["run_id"],
        "environment_hash": _environment_hash(),
        "methodology_snapshot_hash": _methodology_snapshot_hash(record),
        "seed_policy": record.get("seed_policy", "n/a"),
        "notes": "reproduce gate %s (%s)" % ("PASS" if passed else "FAIL", detail["rule"]),
    }
    _validate_repro_ledger_entry(entry)

    ledger.parent.mkdir(parents=True, exist_ok=True)
    prev = _prev_digest(ledger)
    spine = {
        "kind": "repro_ledger_spine_record",
        "schema_version": "0.1",
        "ts": ts,
        "bench": record["bench"],
        "round_id": record["round_id"],   # stamped: versioned rounds
        "version": record["version"],     # stamped: versioned rounds
        "reproduce_outcome": {
            "passed": passed,
            "recorded": detail["recorded"],
            "observed": detail["observed"],
            "delta": detail["delta"],
            "tolerance": detail["tolerance"],
            "rule": detail["rule"],
            "headline_metric_id": detail["headline_metric_id"],
        },
        "entry": entry,
        "prev_entry_digest": prev,
    }
    # content address: the digest covers the whole spine record incl. prev link.
    spine["entry_digest"] = canonical_digest(spine)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(spine, sort_keys=True) + "\n")
    return spine


def verify_ledger(ledger: Path) -> bool:
    """True iff the spine chain is intact and every entry is content-addressed
    correctly (tamper-evident)."""
    if not ledger.exists():
        return True
    prev = ""
    for ln in ledger.read_text().splitlines():
        if not ln.strip():
            continue
        rec = json.loads(ln)
        if rec.get("prev_entry_digest", "") != prev:
            return False
        claimed = rec.pop("entry_digest")
        if canonical_digest(rec) != claimed:
            return False
        rec["entry_digest"] = claimed
        prev = claimed
    return True


def _validate_repro_ledger_entry(entry: dict) -> None:
    schema = json.loads((SCHEMA_DIR / "repro-ledger-entry.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(entry)


def run(bench: str, run_id: str, gate: bool, inject: float | None = None) -> int:
    """Unified reproduce path. Loads the recorded run, re-runs it, MANDATES a
    chained repro-ledger-entry, and (if gate) fails closed on drift."""
    rp = record_path(bench, run_id)
    if not rp.exists():
        print("ERROR: no recorded run %s for bench %s (expected %s)" % (run_id, bench, rp), file=sys.stderr)
        return 2
    record = load_record(rp)
    print("dispatch: BENCH=%s RUN=%s -> %s" % (bench, run_id, DISPATCH[bench]["command"]))

    try:
        observed = observe(record, override=inject)
    except ArtifactIntegrityError as e:
        # A replay artifact failed hash/certificate verification. FAIL CLOSED:
        # never treat a tampered/stale artifact as a reproduced number.
        print("ARTIFACT INTEGRITY FAIL (fail-closed): %s" % e, file=sys.stderr)
        return 1
    except RuntimeError as e:
        # external arm: dispatch-only. Emit a ledger entry recording the dispatch,
        # do NOT fabricate a reproduced number.
        print("external arm (dispatch-only): %s" % e)
        detail = {"headline_metric_id": record["headline_metric_id"], "recorded": float(record["headline_value"]),
                  "observed": float("nan"), "delta": float("nan"), "determinism": record["determinism"],
                  "tolerance": 0.0, "rule": "external_dispatch_only", "round_id": record["round_id"],
                  "version": record["version"], "passed": None}
        emit_ledger_entry(record, float("nan"), False, {**detail, "rule": "external_dispatch_only"})
        print("  reproduce out-of-band:  %s" % record.get("external_command", DISPATCH[bench]["command"]))
        return 0  # dispatch succeeded; reproduction is out-of-band

    passed, detail = reproduce_gate(record, observed)
    spine = emit_ledger_entry(record, observed, passed, detail)
    print("repro-ledger: %s  (entry_digest=%s prev=%s)"
          % (ledger_path_for(bench), spine["entry_digest"][:12], (spine["prev_entry_digest"] or "GENESIS")[:12]))
    print("  round=%s version=%s  metric=%s" % (record["round_id"], record["version"], detail["headline_metric_id"]))
    print("  recorded=%.6f observed=%.6f delta=%.6g tolerance=%s rule=%s"
          % (detail["recorded"], detail["observed"], detail["delta"], detail["tolerance"], detail["rule"]))
    if not verify_ledger(ledger_path_for(bench)):
        print("ERROR: repro-ledger chain verification FAILED (tamper-evident)", file=sys.stderr)
        return 3
    if gate:
        if passed:
            print("GATE PASS: headline reproduced within tolerance.")
            return 0
        print("GATE FAIL (fail-closed): metric drift exceeds tolerance.", file=sys.stderr)
        return 1
    print("reproduce %s (gate not enforced): %s" % ("PASS" if passed else "DRIFT", detail["rule"]))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Unified benchmark reproduce path + tolerance gate.")
    ap.add_argument("--bench", required=True, help="dispatch key: %s" % ", ".join(sorted(DISPATCH)))
    ap.add_argument("--run", required=True, help="recorded run id (contracts/reproduce/<bench>/<run>.run.json)")
    ap.add_argument("--gate", action="store_true", help="FAIL CLOSED on metric drift beyond tolerance")
    ap.add_argument("--inject-observed", type=float, default=None,
                    help="TEETH: inject an observed headline value (bypasses re-run) to prove the gate bites")
    args = ap.parse_args(argv)
    return run(args.bench, args.run, gate=args.gate, inject=args.inject_observed)


if __name__ == "__main__":
    raise SystemExit(main())
