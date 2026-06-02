#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "apps" / "socioprophet-web" / "src" / "components" / "TritFabricReadinessLabels.vue"
CONTRACT = ROOT / "contracts" / "integrations" / "tritfabric-ui-labels.v0.json"


def load_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def validate_component() -> None:
    text = COMPONENT.read_text(encoding="utf-8")
    contract = load_contract()

    required_fragments = [
        "tritfabric-ui-labels.v0.json",
        "TritFabric readiness labels",
        "Governed product-consumption surfaces",
        "Must show",
        "Forbidden badges",
        "Claim boundary",
        "label.must_show",
        "label.forbidden_badges",
        "claimBoundary",
    ]
    for fragment in required_fragments:
        if fragment not in text:
            raise AssertionError(f"component missing required fragment: {fragment}")

    for label in contract.get("labels", []):
        for field in ("surface_id", "display_label", "status_label"):
            value = label.get(field)
            if not value:
                raise AssertionError(f"label missing {field}")
        # The component renders these dynamically from the contract rather than
        # hard-coding each value. We still assert the source contract includes
        # the labels the component is expected to project.
        if not label.get("must_show") or not label.get("forbidden_badges"):
            raise AssertionError(f"label {label['surface_id']} missing gate/badge lists")

    forbidden_runtime_terms = [
        "fetch(",
        "POST",
        "PUT",
        "DELETE",
        "artifact_promotion = true",
        "serve_deployment = true",
        "autoscaler_active_loop = true",
    ]
    for term in forbidden_runtime_terms:
        if term in text:
            raise AssertionError(f"component must not introduce runtime behavior: {term}")


def main() -> int:
    validate_component()
    print("tritfabric UI component: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
