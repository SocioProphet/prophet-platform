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


def load_series(path: Path, time_col: str, value_col: str) -> list[tuple[float, float]]:
    series: list[tuple[float, float]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("CSV requires header")
        for row in reader:
            series.append((float(row[time_col]), float(row[value_col])))
    if len(series) < 3:
        raise ValueError("SINDy MVP requires at least three samples")
    return sorted(series, key=lambda item: item[0])


def finite_difference(series: list[tuple[float, float]]) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for (t0, y0), (t1, y1) in zip(series[:-1], series[1:]):
        dt = t1 - t0
        if dt <= 0:
            raise ValueError("time column must be strictly increasing")
        result.append((y0, (y1 - y0) / dt))
    return result


def fit_linear_dynamics(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        raise ValueError("state variable has zero variance")
    coefficient = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
    intercept = y_mean - coefficient * x_mean
    preds = [coefficient * x + intercept for x in xs]
    mse = sum((y - p) ** 2 for y, p in zip(ys, preds)) / len(ys)
    denom_y = sum((y - y_mean) ** 2 for y in ys) / len(ys)
    nmse = mse / denom_y if denom_y else 0.0
    return coefficient, intercept, nmse


def build_candidate(args: argparse.Namespace) -> dict[str, Any]:
    data_path = Path(args.data)
    series = load_series(data_path, args.time_column, args.value_column)
    derivative_points = finite_difference(series)
    coefficient, intercept, nmse = fit_linear_dynamics(derivative_points)
    equation = f"d{args.value_column}/dt = {coefficient:.12g} {args.value_column} + {intercept:.12g}"
    return {
        "artifactType": "PlatformDynamicsCandidate",
        "applicationMode": "platform_dynamics",
        "candidateId": f"urn:prometheus:platform-dynamics-candidate:{sha256_file(data_path)[:16]}",
        "methodFamily": "sindy",
        "implementationMode": "sindy_linear_fast_path",
        "datasetRef": {
            "uri": args.dataset_uri,
            "contentHash": sha256_file(data_path),
            "hashAlgorithm": "sha256",
        },
        "timeColumn": args.time_column,
        "stateVariable": args.value_column,
        "equationLatex": equation,
        "fitMetric": {"name": "nmse", "value": nmse},
        "complexity": 3,
        "unitsStatus": "unknown",
        "promotionState": "candidate",
        "controlAuthority": False,
        "nonAuthorityDeclaration": "This is a PlatformDynamicsCandidate only. It is not an autoscaling policy, routing policy, remediation policy, controller, or runtime authority.",
        "issuedAt": args.generated_at or now_utc(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PROMETHEUS SINDy fast-path dynamics candidate emitter")
    parser.add_argument("--data", required=True)
    parser.add_argument("--time-column", default="t")
    parser.add_argument("--value-column", required=True)
    parser.add_argument("--dataset-uri", required=True)
    parser.add_argument("--generated-at")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    candidate = build_candidate(args)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(out), "controlAuthority": candidate["controlAuthority"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
