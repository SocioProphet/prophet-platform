#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_csv(path: Path) -> tuple[list[str], list[dict[str, float]]]:
    rows: list[dict[str, float]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("CSV requires header")
        fields = list(reader.fieldnames)
        for row in reader:
            rows.append({k: float(v) for k, v in row.items() if k is not None and v not in (None, "")})
    if not rows:
        raise ValueError("CSV requires at least one row")
    return fields, rows


def fit_linear_one_feature(rows: list[dict[str, float]], x_name: str, y_name: str) -> tuple[float, float, float]:
    xs = [row[x_name] for row in rows]
    ys = [row[y_name] for row in rows]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        raise ValueError("feature has zero variance")
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
    intercept = y_mean - slope * x_mean
    preds = [slope * x + intercept for x in xs]
    mse = sum((y - p) ** 2 for y, p in zip(ys, preds)) / len(ys)
    denom_y = sum((y - y_mean) ** 2 for y in ys) / len(ys)
    nmse = mse / denom_y if denom_y else 0.0
    return slope, intercept, nmse


def equation_text(target: str, feature: str, slope: float, intercept: float) -> tuple[str, int]:
    if abs(intercept) < 1e-12:
        return f"{target} = {slope:.12g} {feature}", 3
    sign = "+" if intercept >= 0 else "-"
    return f"{target} = {slope:.12g} {feature} {sign} {abs(intercept):.12g}", 5


def units_status(target_unit: str | None, feature_units: dict[str, str], feature: str) -> str:
    if not target_unit or feature not in feature_units:
        return "unknown"
    try:
        import sympy as sp
        from sympy.physics import units as u
    except Exception:
        return "unchecked"
    namespace = {name: getattr(u, name) for name in dir(u) if not name.startswith("_")}
    try:
        target = sp.sympify(target_unit, locals=namespace)
        source = sp.sympify(feature_units[feature], locals=namespace)
    except Exception:
        return "unknown"
    return "consistent" if sp.simplify(target / source).is_number else "inconsistent"


def build_artifact(args: argparse.Namespace) -> dict[str, Any]:
    if args.engine == "optional_ai_descartes" and not args.allow_fixture:
        raise RuntimeError(
            "optional_ai_descartes requested before runtime pinning is available; "
            "use --allow-fixture to emit the deterministic PROMETHEUS-owned fixture"
        )

    data_path = Path(args.data)
    fields, rows = load_csv(data_path)
    if args.target not in fields:
        raise ValueError(f"target not found: {args.target}")
    features = [f for f in fields if f != args.target]
    if len(features) != 1:
        raise ValueError("AI-Descartes MVP fixture supports exactly one feature plus target")
    feature = features[0]

    slope, intercept, nmse = fit_linear_one_feature(rows, feature, args.target)
    latex, complexity = equation_text(args.target, feature, slope, intercept)
    feature_units: dict[str, str] = {}
    if args.feature_unit:
        for pair in args.feature_unit:
            name, unit = pair.split("=", 1)
            feature_units[name] = unit
    u_status = units_status(args.target_unit, feature_units, feature)
    data_hash = sha256_file(data_path)
    implementation_mode = "fixture_ai_descartes" if args.engine == "fixture_ai_descartes" else "optional_ai_descartes_fixture_fallback"

    return {
        "artifactType": "EquationCandidate",
        "applicationMode": "scientific_law_discovery",
        "candidateId": f"urn:prometheus:equation-candidate:ai-descartes:{data_hash[:16]}",
        "methodFamily": "ai_descartes",
        "implementationMode": implementation_mode,
        "engineMode": args.engine,
        "vendorRuntimeUsed": False,
        "priorArtRef": "ibm:ai-descartes",
        "datasetRef": {
            "uri": args.dataset_uri,
            "contentHash": data_hash,
            "hashAlgorithm": "sha256",
        },
        "target": args.target,
        "features": features,
        "equationLatex": latex,
        "fitMetric": {"name": "nmse", "value": nmse},
        "complexity": complexity,
        "unitsStatus": u_status,
        "backgroundTheoryRefs": [
            {
                "uri": args.background_theory_uri,
                "status": "fixture_only",
                "nonAuthorityDeclaration": "Background theory is advisory fixture context only and does not authorize law admission.",
            }
        ],
        "experimentDesignPosture": "not_requested",
        "promotionState": "candidate" if u_status != "inconsistent" else "rejected",
        "nonAuthorityDeclaration": "This AI-Descartes-style EquationCandidate is not a law, ontology assertion, policy, controller, runtime authority, deployment authorization, or admitted SRAssertion.",
        "issuedAt": args.generated_at or now_utc(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PROMETHEUS AI-Descartes-style MVP candidate emitter")
    parser.add_argument("--data", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--dataset-uri", required=True)
    parser.add_argument("--target-unit")
    parser.add_argument("--feature-unit", action="append", default=[])
    parser.add_argument("--background-theory-uri", default="urn:prometheus:background-theory:fixture:linear-proportionality")
    parser.add_argument("--generated-at")
    parser.add_argument("--output", required=True)
    parser.add_argument("--engine", choices=["fixture_ai_descartes", "optional_ai_descartes"], default="fixture_ai_descartes")
    parser.add_argument("--allow-fixture", action="store_true")
    args = parser.parse_args()
    artifact = build_artifact(args)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(out), "unitsStatus": artifact["unitsStatus"], "implementationMode": artifact["implementationMode"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
