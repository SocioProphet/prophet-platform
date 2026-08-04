#!/usr/bin/env python3
"""Unit-test the SLO recording rules with promtool, against the REAL applied artifact.

infra/k8s/observability/base/prometheusrule-slos.yaml is a Kubernetes PrometheusRule CRD, not a
plain Prometheus rule file -- `promtool test rules` needs the latter. This extracts spec.groups
from the real manifest at test time (never a hand-duplicated copy that could drift from what's
actually applied) and runs slo_rules_test.yml.tmpl against it via promtool.

Requires `promtool` on PATH (part of the Prometheus release, `brew install prometheus` locally;
CI installs it explicitly). Exits non-zero and prints promtool's own diff on any failure.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "infra" / "k8s" / "observability" / "base" / "prometheusrule-slos.yaml"
TEMPLATE = ROOT / "tools" / "fixtures" / "slo_rules_test.yml.tmpl"


def main() -> int:
    if shutil.which("promtool") is None:
        print("SKIP: promtool not on PATH (install: brew install prometheus, or apt-get install prometheus)")
        return 0

    doc = yaml.safe_load(MANIFEST.read_text())
    groups = (doc.get("spec") or {}).get("groups")
    if not groups:
        print(f"FAIL: {MANIFEST} has no spec.groups -- nothing to test")
        return 1

    with tempfile.TemporaryDirectory() as td:
        rules_path = Path(td) / "rules-plain.yaml"
        rules_path.write_text(yaml.safe_dump({"groups": groups}, sort_keys=False))

        test_path = Path(td) / "slo_rules_test.yml"
        test_path.write_text(TEMPLATE.read_text().replace("__RULES_FILE__", str(rules_path)))

        result = subprocess.run(["promtool", "test", "rules", str(test_path)], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            print("FAIL: promtool test rules — see diff above")
            return 1
    print("OK: SLO recording rules pass their promtool unit tests (zero-5xx, absent-metrics, real-breach cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
