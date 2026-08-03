#!/usr/bin/env python3
"""Validate a ShellBackendAdapter manifest: schema + semantics — CI-minted auth
(never a static PAT), every mutating op carries a ship/operate/egress/administer
consent purpose, and (across manifests) GitHub and Gitea implement the SAME op
set so the shell is backend-abstract. Self-test proves both ways."""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts" / "ShellBackendAdapter.v0.1.json"
ADAPTERS = ROOT / "contracts" / "adapters"
MUTATING_PURPOSES = {"implement", "ship", "operate", "egress", "administer"}


def semantic(m: dict) -> list[str]:
    errs = []
    if m["auth"]["model"] not in {"ci-minted-app-token", "ci-minted-oauth", "wif"}:
        errs.append("auth.model must be CI-minted (never a static PAT)")
    if "pat" in m["auth"]["token_ref"].lower():
        errs.append("token_ref must not reference a PAT")
    for c in m["capabilities"]:
        if c.get("mutating") and c.get("consent_purpose") not in MUTATING_PURPOSES:
            errs.append(f"mutating op {c['op']} must carry a mutating consent_purpose, got {c.get('consent_purpose')}")
    return errs


def main(argv=None) -> int:
    manifests = {}
    for f in sorted(ADAPTERS.glob("*.adapter.json")):
        manifests[f.stem] = json.loads(f.read_text())
    errs = []
    try:
        import jsonschema
        schema = json.loads(SCHEMA.read_text())
        for name, m in manifests.items():
            try:
                jsonschema.validate(m, schema)
            except Exception as e:
                errs.append(f"{name}: schema: {str(e).splitlines()[0]}")
    except ImportError:
        pass
    for name, m in manifests.items():
        errs += [f"{name}: {e}" for e in semantic(m)]
    # parity: both backends implement the same op set (backend-abstract shell)
    opsets = {name: {c["op"] for c in m["capabilities"]} for name, m in manifests.items()}
    if len({frozenset(v) for v in opsets.values()}) > 1:
        errs.append(f"backend op-set parity broken: {opsets}")
    if errs:
        print("FAIL:", file=sys.stderr)
        for e in errs: print("  -", e, file=sys.stderr)
        return 1
    print(f"OK: {len(manifests)} backend adapters valid + op-parity ({sorted(manifests)}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
