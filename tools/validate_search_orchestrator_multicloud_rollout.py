from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MATRIX = ROOT / "releases/evidence/search-orchestrator-academy-multicloud-rollout-matrix.v0.1.json"
GUIDE = ROOT / "docs/SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_MULTICLOUD_ROLLOUT_PREP.md"
TEMPLATE = ROOT / "releases/evidence/search-orchestrator-academy-rollout-evidence.template.json"

REQUIRED_GLOBAL = {
    "aws",
    "azure",
    "google-cloud",
    "oracle-cloud",
    "ibm-cloud",
    "alibaba-cloud",
    "huawei-cloud",
    "tencent-cloud",
}

REQUIRED_REGIONS = {
    "north_america",
    "south_america",
    "europe",
    "middle_east",
    "africa",
    "asia_pacific",
    "china_mainland",
}

REQUIRED_EVIDENCE = {
    "rendered_manifests",
    "argocd_sync",
    "healthz",
    "debug_config",
    "debug_metrics",
    "academy_ingest_query",
    "lampstand_carrier_artifacts",
    "rollback_verification",
    "image_digest_pin_verification",
    "secret_or_externalsecret_binding",
    "pvc_storage_class_binding",
    "network_policy_or_cni_exception",
}

REQUIRED_OPENSHIFT = {
    "openshift",
    "okd",
    "generic-kubernetes",
}

REQUIRED_GUIDE_TERMS = [
    "Google Cloud",
    "Azure",
    "AWS",
    "IBM Cloud",
    "Oracle Cloud",
    "OpenShift",
    "OKD",
    "BYOC/self-hosted",
    "NetworkPolicy",
    "ExternalSecret",
]


def main() -> int:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    guide = GUIDE.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")

    missing_global = REQUIRED_GLOBAL.difference(matrix.get("global_hyperscalers", []))
    if missing_global:
        raise SystemExit(f"missing global providers: {sorted(missing_global)}")

    region_map = matrix.get("regional_provider_coverage", {})
    missing_regions = REQUIRED_REGIONS.difference(region_map)
    if missing_regions:
        raise SystemExit(f"missing regional provider coverage: {sorted(missing_regions)}")

    for region, providers in region_map.items():
        if not providers:
            raise SystemExit(f"region {region} has no providers")

    missing_evidence = REQUIRED_EVIDENCE.difference(matrix.get("provider_evidence_required", []))
    if missing_evidence:
        raise SystemExit(f"missing evidence requirements: {sorted(missing_evidence)}")

    openshift_targets = set(matrix.get("openshift_compatibility", {}).get("targets", []))
    missing_targets = REQUIRED_OPENSHIFT.difference(openshift_targets)
    if missing_targets:
        raise SystemExit(f"missing OpenShift compatibility targets: {sorted(missing_targets)}")

    controls = "\n".join(matrix.get("openshift_compatibility", {}).get("required_controls", []))
    for term in ["runAsNonRoot", "allowPrivilegeEscalation=false", "RuntimeDefault seccomp", "no privileged containers", "PVC-backed carrier storage"]:
        if term not in controls:
            raise SystemExit(f"missing OpenShift control: {term}")

    for term in REQUIRED_GUIDE_TERMS:
        if term not in guide:
            raise SystemExit(f"guide missing term: {term}")

    for term in ["template-pending-real-cluster-capture", "rendered_manifests", "rollback_verification"]:
        if term not in template:
            raise SystemExit(f"template missing term: {term}")

    print("search-orchestrator multicloud rollout preparation validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
