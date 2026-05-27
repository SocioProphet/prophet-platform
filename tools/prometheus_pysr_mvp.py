#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
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
    data_path = Path(args.data)
    fields, rows = load_csv(data_path)
    if args.target not in fields:
        raise ValueError(f"target not found: {args.target}")
    features = [f for f in fields if f != args.target]
    if len(features) != 1:
        raise ValueError("MVP supports exactly one feature plus target")
    feature = features[0]
    slope, intercept, nmse = fit_linear_one_feature(rows, feature, args.target)
    feature_units = {}
    if args.feature_unit:
        for pair in args.feature_unit:
            name, unit = pair.split("=", 1)
            feature_units[name] = unit
    u_status = units_status(args.target_unit, feature_units, feature)
    latex = f"{args.target} = {slope:.12g} {feature} + {intercept:.12g}"
    candidate_id = f"urn:prometheus:equation-candidate:{sha256_file(data_path)[:16]}"
    return {
        "artifactType": "EquationCandidate",
        "applicationMode": "equation_discovery",
        "candidateId": candidate_id,
        "methodFamily": "pysr",
        "implementationMode": "mvp_linear_fallback",
        "datasetRef": {
            "uri": args.dataset_uri,
            "contentHash": sha256_file(data_path),
            "hashAlgorithm": "sha256",
        },
        "target": args.target,
        "features": features,
        "equationLatex": latex,
        "fitMetric": {"name": "nmse", "value": nmse},
        "complexity": 3,
        "unitsStatus": u_status,
        "promotionState": "candidate" if u_status != "inconsistent" else "rejected",
        "nonAuthorityDeclaration": "This is an EquationCandidate only. It is not a law, ontology assertion, policy, or controller.",
        "issuedAt": args.generated_at or now_utc(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PROMETHEUS PySR MVP candidate emitter")
    parser.add_argument("--data", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--dataset-uri", required=True)
    parser.add_argument("--target-unit")
    parser.add_argument("--feature-unit", action="append", default=[])
    parser.add_argument("--generated-at")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    artifact = build_artifact(args)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(out), "unitsStatus": artifact["unitsStatus"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
