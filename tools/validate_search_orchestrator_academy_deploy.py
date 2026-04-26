from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "infra/k8s/search-orchestrator/base/kustomization.yaml",
    "infra/k8s/search-orchestrator/base/deployment.yaml",
    "infra/k8s/search-orchestrator/base/service.yaml",
    "infra/k8s/search-orchestrator/base/configmap.yaml",
    "infra/k8s/search-orchestrator/overlays/lab/kustomization.yaml",
    "infra/k8s/search-orchestrator/overlays/carrier/kustomization.yaml",
    "infra/k8s/search-orchestrator/overlays/policy/kustomization.yaml",
    "infra/argocd/appsets/search-orchestrator-academy-appset.yaml",
    "bundles/fogstack.knowledge-v0.1.yaml",
    "services/search-orchestrator/deploy/academy-bridge-profiles.yaml",
    "infra/local/docker-compose.search-orchestrator.academy.yml",
    "services/search-orchestrator/tests/test_academy_lampstand_deployment_smoke.py",
    "docs/SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_ROLLOUT_CHECKLIST.md",
    "docs/SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_RELEASE_READOUT.md",
    "releases/evidence/search-orchestrator.academy-bridge.validation.record.json",
    "releases/manifests/search-orchestrator.academy-bridge.manifest.json",
    "infra/k8s/argo-cd/appsets/socioprophet-appset.yaml",
]

REQUIRED_TEXT = {
    "infra/k8s/search-orchestrator/overlays/carrier/configmap-patch.yaml": [
        "SEARCH_ORCHESTRATOR_ACADEMY_LAMPSTAND_CARRIER_DIR",
        "SOCIOPROFIT_STATE_HOME",
    ],
    "infra/k8s/search-orchestrator/overlays/policy/configmap-patch.yaml": [
        "SEARCH_ORCHESTRATOR_POLICY_FABRIC_ENDPOINT",
    ],
    "infra/argocd/appsets/search-orchestrator-academy-appset.yaml": [
        "search-orchestrator-academy-carrier",
        "search-orchestrator-academy-policy",
        "infra/k8s/search-orchestrator/overlays/carrier",
        "infra/k8s/search-orchestrator/overlays/policy",
    ],
    "bundles/fogstack.knowledge-v0.1.yaml": [
        "services/search-orchestrator",
        "academy-search-bridge",
        "LearningSearchRecord",
        "AcademySearchVisibilityRequestV1",
        "infra/argocd/appsets/search-orchestrator-academy-appset.yaml",
    ],
    "docs/SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_ROLLOUT_CHECKLIST.md": [
        "Recommended rollout order",
        "Health gates",
        "Rollback plan",
        "Failure modes and remediation",
        "SEARCH_ORCHESTRATOR_ACADEMY_LAMPSTAND_CARRIER_DIR",
        "SEARCH_ORCHESTRATOR_POLICY_FABRIC_ENDPOINT",
    ],
    "docs/SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_RELEASE_READOUT.md": [
        "End-to-end path",
        "Policy Fabric",
        "Lampstand carrier",
        "FogStack release evidence",
        "Known gaps",
    ],
    "releases/evidence/search-orchestrator.academy-bridge.validation.record.json": [
        "search-orchestrator-academy-bridge",
        "test_academy_lampstand_deployment_smoke.py",
        "search-orchestrator-academy-appset.yaml",
        "SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_ROLLOUT_CHECKLIST.md",
        "SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_RELEASE_READOUT.md",
    ],
    "releases/manifests/search-orchestrator.academy-bridge.manifest.json": [
        "search-orchestrator.academy-bridge.v0.1",
        "search-orchestrator-academy-appset.yaml",
        "fogstack.knowledge-v0.1.yaml",
        "SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_ROLLOUT_CHECKLIST.md",
        "SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_RELEASE_READOUT.md",
    ],
    "infra/k8s/argo-cd/appsets/socioprophet-appset.yaml": [
        "kind: ApplicationSet",
        "search-orchestrator-academy-bridge",
        "infra/k8s/search-orchestrator/overlays/policy",
        "bundle: fogstack.knowledge",
    ],
}


def main() -> int:
    for rel in REQUIRED:
        path = ROOT / rel
        if not path.exists():
            raise SystemExit(f"missing required deployment artifact: {rel}")
        if not path.read_text(encoding="utf-8").strip():
            raise SystemExit(f"empty deployment artifact: {rel}")

    for rel, terms in REQUIRED_TEXT.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for term in terms:
            if term not in text:
                raise SystemExit(f"{rel} missing required term {term}")

    print("search-orchestrator academy deployment artifacts validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
