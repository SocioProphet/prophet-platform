#!/usr/bin/env python3
"""Validate the Regis ACR Prophet Platform integration surface."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "docs/REGIS_ACR_SERVICE_INTEGRATION.md",
    "contracts/acr/regis-acr-platform-contract.yaml",
    "apps/regis-acr-api/requirements.txt",
    "apps/regis-acr-api/src/regis_acr_api/main.py",
    "tools/smoke_regis_acr_service.py",
]

try:
    import yaml  # type: ignore
except Exception as exc:  # pragma: no cover
    print(f"ERROR: PyYAML is required for contract validation: {exc}", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    errors: List[str] = []

    for rel in REQUIRED_PATHS:
        if not (ROOT / rel).exists():
            errors.append(f"missing required path: {rel}")

    contract_path = ROOT / "contracts" / "acr" / "regis-acr-platform-contract.yaml"
    if contract_path.exists():
        try:
            contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"invalid YAML: {contract_path}: {exc}")
        else:
            if contract.get("service") != "regis-acr-api":
                errors.append("contract service must be regis-acr-api")
            runtime_contracts = contract.get("runtime_contracts") or {}
            for method in [
                "RegisAcr.Health.Ping",
                "RegisAcr.IngestSourceRecord",
                "RegisAcr.ProposeConcordance",
                "RegisAcr.EvaluatePromotion",
            ]:
                if method not in runtime_contracts:
                    errors.append(f"missing runtime contract: {method}")
            safety = contract.get("safety_invariants") or []
            safety_ids = {entry.get("id") for entry in safety if isinstance(entry, dict)}
            for invariant in [
                "no_auto_canonical_merge",
                "decision_receipt_required",
                "low_margin_blocks_promotion",
                "identity_prime_scope_protection",
                "ontogenesis_hook_not_forced",
            ]:
                if invariant not in safety_ids:
                    errors.append(f"missing safety invariant: {invariant}")

    service_main = ROOT / "apps" / "regis-acr-api" / "src" / "regis_acr_api" / "main.py"
    if service_main.exists():
        text = service_main.read_text(encoding="utf-8")
        for token in [
            "/healthz",
            "/v1/source-records",
            "/v1/concordance/proposals",
            "/v1/promotion/evaluate",
            "/v1/relationships/formation-hooks",
            "canonical_mutation",
            "receipt",
        ]:
            if token not in text:
                errors.append(f"service missing expected token: {token}")

    if errors:
        print("ERRORS:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(json.dumps({"ok": True, "integration": "regis-acr-api", "required_paths": len(REQUIRED_PATHS)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
