#!/usr/bin/env python3
"""CLI for model zoo dry-runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from .model_zoo import demo_model_zoo_entry
from .model_zoo_enrichment import enrich_model_zoo_fixture
from .model_zoo_promotion import demo_model_zoo_promotion_bundle, promotion_evidence, promotion_to_platform_record


def emit_demo(args: argparse.Namespace) -> int:
    fixture = demo_model_zoo_entry()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = args.output_dir / "model-zoo-fixture.json"
    enrichment_path = args.output_dir / "model-zoo-enrichment.json"
    records_path = args.output_dir / "model-zoo-platform-records.json"
    fixture_path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    enrichment_path.write_text(json.dumps(enrich_model_zoo_fixture(fixture), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    records_path.write_text(json.dumps(fixture["platformRecords"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(fixture_path), str(enrichment_path), str(records_path)]}, indent=2, sort_keys=True))
    return 0


def emit_promotion_bundle(args: argparse.Namespace) -> int:
    bundle = demo_model_zoo_promotion_bundle()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = args.output_dir / "model-zoo-promotion-bundle.json"
    evidence_path = args.output_dir / "model-zoo-promotion-evidence.json"
    record_path = args.output_dir / "model-zoo-promotion-platform-record.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(promotion_evidence(bundle), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_path.write_text(json.dumps(promotion_to_platform_record(bundle), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(bundle_path), str(evidence_path), str(record_path)]}, indent=2, sort_keys=True))
    return 0


def emit_serving_manifests(args: argparse.Namespace) -> int:
    bundle = demo_model_zoo_promotion_bundle()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    backend_filenames = {
        "ray-serve": "ray-serve.yaml",
        "kserve": "kserve.yaml",
        "seldon-core": "seldon.yaml",
    }
    for manifest_dict in bundle["servingManifests"]:
        backend = manifest_dict["servingBackend"]
        filename = backend_filenames.get(backend, f"{backend}.yaml")
        manifest_path = args.output_dir / filename
        manifest_path.write_text(yaml.dump(manifest_dict["manifest"], default_flow_style=False), encoding="utf-8")
        written.append(str(manifest_path))
    print(json.dumps({"written": written}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lattice Studio model zoo compiler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("emit-demo", help="Emit demo model zoo entry + enrichment + platform records")
    demo.add_argument("--output-dir", type=Path, required=True)
    demo.set_defaults(func=emit_demo)

    promotion = subparsers.add_parser("emit-promotion-bundle", help="Emit demo model zoo promotion bundle + evidence + platform record")
    promotion.add_argument("--output-dir", type=Path, required=True)
    promotion.set_defaults(func=emit_promotion_bundle)

    manifests = subparsers.add_parser("emit-serving-manifests", help="Emit serving manifests as individual YAML files per backend")
    manifests.add_argument("--output-dir", type=Path, required=True)
    manifests.set_defaults(func=emit_serving_manifests)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"lattice-model-zoo: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
