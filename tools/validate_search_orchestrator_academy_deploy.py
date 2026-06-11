from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "services/search-orchestrator/Dockerfile",
    ".github/workflows/search-orchestrator-image.yml",
    "releases/images/search-orchestrator.image-lock.example.json",
    "tools/render_search_orchestrator_image_patch.py",
    "tools/validate_search_orchestrator_image_release.py",
    "infra/k8s/search-orchestrator/base/kustomization.yaml",
    "infra/k8s/search-orchestrator/base/deployment.yaml",
    "infra/k8s/search-orchestrator/base/service.yaml",
    "infra/k8s/search-orchestrator/base/configmap.yaml",
    "infra/k8s/search-orchestrator/base/serviceaccount-rbac.yaml",
    "infra/k8s/search-orchestrator/base/pvc.yaml",
    "infra/k8s/search-orchestrator/base/networkpolicy.yaml",
    "infra/k8s/search-orchestrator/overlays/lab/kustomization.yaml",
    "infra/k8s/search-orchestrator/overlays/carrier/kustomization.yaml",
    "infra/k8s/search-orchestrator/overlays/policy/kustomization.yaml",
    "infra/k8s/search-orchestrator/overlays/policy/deployment-patch.yaml",
    "infra/argocd/appsets/search-orchestrator-academy-appset.yaml",
    "bundles/fogstack.knowledge-v0.1.yaml",
    "services/search-orchestrator/deploy/academy-bridge-profiles.yaml",
    "infra/local/docker-compose.search-orchestrator.academy.yml",
    "services/search-orchestrator/app/metrics.py",
    "services/search-orchestrator/tests/test_academy_lampstand_deployment_smoke.py",
    "services/search-orchestrator/tests/test_debug_metrics.py",
    "docs/SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_ROLLOUT_CHECKLIST.md",
    "docs/SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_RELEASE_READOUT.md",
    "docs/SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_PRODUCTION_HARDENING.md",
    "docs/SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_OBSERVABILITY.md",
    "releases/evidence/search-orchestrator.academy-bridge.validation.record.json",
    "releases/manifests/search-orchestrator.academy-bridge.manifest.json",
    "infra/k8s/argo-cd/appsets/socioprophet-appset.yaml",
]

REQUIRED_TEXT = {
    "services/search-orchestrator/Dockerfile": [
        "FROM python:3.12-slim",
        "USER 10001:10001",
        "uvicorn",
    ],
    ".github/workflows/search-orchestrator-image.yml": [
        "docker/build-push-action",
        "ghcr.io/socioprophet/prophet-platform/search-orchestrator",
        "steps.build.outputs.digest",
        "search-orchestrator-image-evidence",
    ],
    "releases/images/search-orchestrator.image-lock.example.json": [
        "search-orchestrator-image-lock-example",
        "pinned_ref",
        "sha256:REPLACE_WITH_IMAGE_DIGEST",
    ],
    "tools/render_search_orchestrator_image_patch.py": [
        "Render a digest-pinned Search Orchestrator deployment patch",
        "pinned_ref",
        "Deployment",
    ],
    "tools/validate_search_orchestrator_image_release.py": [
        "search-orchestrator image release artifacts validated",
        "pinned_ref",
        "digest form",
    ],
    "infra/k8s/search-orchestrator/base/kustomization.yaml": [
        "serviceaccount-rbac.yaml",
        "pvc.yaml",
        "networkpolicy.yaml",
    ],
    "infra/k8s/search-orchestrator/base/deployment.yaml": [
        "serviceAccountName: search-orchestrator",
        "runAsNonRoot: true",
        "readOnlyRootFilesystem: true",
        "allowPrivilegeEscalation: false",
        "persistentVolumeClaim",
        "search-orchestrator-data",
        "resources:",
    ],
    "infra/k8s/search-orchestrator/base/serviceaccount-rbac.yaml": [
        "kind: ServiceAccount",
        "kind: Role",
        "kind: RoleBinding",
    ],
    "infra/k8s/search-orchestrator/base/pvc.yaml": [
        "kind: PersistentVolumeClaim",
        "ReadWriteOnce",
        "storage: 5Gi",
    ],
    "infra/k8s/search-orchestrator/base/networkpolicy.yaml": [
        "kind: NetworkPolicy",
        "policyTypes:",
        "Ingress",
        "Egress",
    ],
    "infra/k8s/search-orchestrator/overlays/carrier/configmap-patch.yaml": [
        "SEARCH_ORCHESTRATOR_ACADEMY_LAMPSTAND_CARRIER_DIR",
        "SOCIOPROFIT_STATE_HOME",
    ],
    "infra/k8s/search-orchestrator/overlays/policy/configmap-patch.yaml": [
        "SEARCH_ORCHESTRATOR_POLICY_FABRIC_TIMEOUT_SECONDS",
    ],
    "infra/k8s/search-orchestrator/overlays/policy/deployment-patch.yaml": [
        "SEARCH_ORCHESTRATOR_POLICY_FABRIC_ENDPOINT",
        "search-orchestrator-policy-fabric",
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
    "services/search-orchestrator/app/metrics.py": [
        "academy_ingest_total",
        "search_query_total",
        "policy_decision_fallback_total",
    ],
    "services/search-orchestrator/tests/test_debug_metrics.py": [
        "/v1/search/debug/metrics",
        "academy_ingest_total",
    ],
    "docs/SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_PRODUCTION_HARDENING.md": [
        "ServiceAccount",
        "PersistentVolumeClaim",
        "NetworkPolicy",
        "readOnlyRootFilesystem",
        "runAsNonRoot",
    ],
    "docs/SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_OBSERVABILITY.md": [
        "/v1/search/debug/metrics",
        "academy_ingest_total",
        "policy_decision_fallback_total",
        "Dashboard panels",
        "Incident workflow",
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
    "releases/evidence/search-orchestrator.academy-bridge.validation.record.json": [
        "test_debug_metrics.py",
        "networkpolicy.yaml",
        "search-orchestrator-image.yml",
        "search-orchestrator.image-lock.example.json",
        "SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_PRODUCTION_HARDENING.md",
        "SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_OBSERVABILITY.md",
    ],
    "releases/manifests/search-orchestrator.academy-bridge.manifest.json": [
        "networkpolicy.yaml",
        "test_debug_metrics.py",
        "search-orchestrator-image.yml",
        "search-orchestrator.image-lock.example.json",
        "SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_PRODUCTION_HARDENING.md",
        "SEARCH_ORCHESTRATOR_ACADEMY_BRIDGE_OBSERVABILITY.md",
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
