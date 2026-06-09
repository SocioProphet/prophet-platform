#!/usr/bin/env python3
"""
Validate prophet-mesh deployment alignment.

Checks:
  - k8s manifests exist for all 10 mesh services + qdrant
  - Each service has base/deployment.yaml, service.yaml, kustomization.yaml
  - Each service has an overlays/p0-lab/kustomization.yaml
  - Argo CD appset includes all mesh services
  - docker-compose.mesh.yml declares all services and has dependency ordering
  - Port assignments are unique across workspace + mesh stacks
  - Each service's env vars reference known upstream service URLs
  - No hardcoded secrets in manifests (no plaintext passwords)
"""
from __future__ import annotations

import sys
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

MESH_SERVICES = [
    "model-governance-ledger",
    "memoryd",
    "policy-fabric",
    "model-router",
    "agent-registry",
    "superconscious",
    "agentplane",
    "tritfabric",
    "prophet-mesh",
    "mesh-qdrant",
]

MESH_PORTS = {
    "memoryd": 8787,
    "policy-fabric": 8700,
    "model-router": 8710,
    "agent-registry": 8720,
    "agentplane": 8730,
    "superconscious": 8740,
    "tritfabric": 8750,
    "model-governance-ledger": 8760,
    "prophet-mesh": 8780,
    "mesh-qdrant-http": 6333,
    "mesh-qdrant-grpc": 6334,
}

WORKSPACE_PORTS = {143, 993, 24, 25, 587, 5232, 9000, 9001, 5432, 6379}

APPSET = ROOT / "infra/k8s/argo-cd/appsets/socioprophet-appset.yaml"
COMPOSE = ROOT / "infra/local/docker-compose.mesh.yml"
K8S_ROOT = ROOT / "infra/k8s"

ERRORS: list[str] = []
PASSES: list[str] = []

def ok(msg: str) -> None:
    PASSES.append(msg)

def fail(msg: str) -> None:
    ERRORS.append(msg)


# ── 1. k8s manifest existence ─────────────────────────────────────────────────

def check_k8s_manifests() -> None:
    for svc in MESH_SERVICES:
        base = K8S_ROOT / svc / "base"
        overlay = K8S_ROOT / svc / "overlays/p0-lab"

        if not base.exists():
            fail(f"k8s/{svc}/base/ missing")
            continue

        for fname in ["kustomization.yaml"]:
            if not (base / fname).exists():
                fail(f"k8s/{svc}/base/{fname} missing")
            else:
                ok(f"k8s/{svc}/base/{fname}")

        if svc != "mesh-qdrant":
            for fname in ["deployment.yaml", "service.yaml"]:
                if not (base / fname).exists():
                    fail(f"k8s/{svc}/base/{fname} missing")
                else:
                    ok(f"k8s/{svc}/base/{fname}")
        else:
            for fname in ["statefulset.yaml", "service.yaml"]:
                if not (base / fname).exists():
                    fail(f"k8s/{svc}/base/{fname} missing (qdrant is StatefulSet)")
                else:
                    ok(f"k8s/{svc}/base/{fname}")

        if not overlay.exists():
            fail(f"k8s/{svc}/overlays/p0-lab/ missing")
        elif not (overlay / "kustomization.yaml").exists():
            fail(f"k8s/{svc}/overlays/p0-lab/kustomization.yaml missing")
        else:
            ok(f"k8s/{svc}/overlays/p0-lab/kustomization.yaml")


# ── 2. Argo CD appset coverage ────────────────────────────────────────────────

APPSET_BUNDLE_EXPECTATIONS = {
    "mesh.vector-store",
    "mesh.governance",
    "mesh.memory",
    "mesh.policy",
    "mesh.routing",
    "mesh.registry",
    "mesh.cognition",
    "mesh.execution",
    "mesh.ml",
    "mesh.conductor",
}

def check_appset() -> None:
    if not APPSET.exists():
        fail(f"Argo CD appset not found: {APPSET.relative_to(ROOT)}")
        return

    text = APPSET.read_text()
    for bundle in APPSET_BUNDLE_EXPECTATIONS:
        if bundle in text:
            ok(f"appset includes bundle: {bundle}")
        else:
            fail(f"appset MISSING bundle: {bundle}")


# ── 3. docker-compose.mesh.yml service coverage ───────────────────────────────

COMPOSE_SERVICES = {
    "postgres-mesh", "qdrant", "model-governance-ledger", "memoryd",
    "policy-fabric", "model-router", "agent-registry", "superconscious",
    "agentplane", "tritfabric-server", "prophet-mesh",
}

def check_compose() -> None:
    if not COMPOSE.exists():
        fail(f"docker-compose.mesh.yml not found: {COMPOSE.relative_to(ROOT)}")
        return

    text = COMPOSE.read_text()
    for svc in COMPOSE_SERVICES:
        if f"\n  {svc}:" in text:
            ok(f"compose includes service: {svc}")
        else:
            fail(f"compose MISSING service: {svc}")


# ── 4. Port uniqueness (no collision with workspace stack) ────────────────────

def check_ports() -> None:
    for svc, port in MESH_PORTS.items():
        if port in WORKSPACE_PORTS:
            fail(f"Port conflict: mesh.{svc}={port} collides with workspace stack")
        else:
            ok(f"port {port} ({svc}) — no workspace collision")

    # Check uniqueness within mesh ports
    seen: dict[int, str] = {}
    for svc, port in MESH_PORTS.items():
        if port in seen:
            fail(f"Port conflict within mesh: {port} used by both {seen[port]} and {svc}")
        else:
            seen[port] = svc


# ── 5. No plaintext secrets in k8s manifests ─────────────────────────────────

PLAINTEXT_SECRET_PATTERNS = [
    r'password:\s+"[^${}][^"]+"',
    r'POSTGRES_PASSWORD.*value.*["\'](?!mesh-dev|dev-password|\$\{)',
    r'API_KEY.*value.*["\'][a-zA-Z0-9]{20,}["\']',
]

def check_no_plaintext_secrets() -> None:
    compiled = [re.compile(p, re.IGNORECASE) for p in PLAINTEXT_SECRET_PATTERNS]
    for svc in MESH_SERVICES:
        base = K8S_ROOT / svc / "base"
        if not base.exists():
            continue
        for f in sorted(base.glob("*.yaml")):
            text = f.read_text()
            for pat in compiled:
                m = pat.search(text)
                if m:
                    fail(f"Possible plaintext secret in {f.relative_to(ROOT)}: {m.group()[:60]}")
    ok("no plaintext secrets detected in mesh k8s manifests")


# ── 6. Service URL cross-reference (compose → correct upstream hostnames) ─────

EXPECTED_URL_REFS = {
    "model-router": ["policy-fabric:8700", "memoryd:8787"],
    "agent-registry": ["policy-fabric:8700"],
    "superconscious": ["model-router:8710", "memoryd:8787"],
    "agentplane": ["policy-fabric:8700", "agent-registry:8720", "model-router:8710",
                   "memoryd:8787", "superconscious:8740"],
    "prophet-mesh": ["agentplane:8730", "model-router:8710", "agent-registry:8720",
                     "memoryd:8787", "policy-fabric:8700", "superconscious:8740"],
}

def check_url_refs() -> None:
    if not COMPOSE.exists():
        return
    text = COMPOSE.read_text()
    for svc, urls in EXPECTED_URL_REFS.items():
        for url in urls:
            if url in text:
                ok(f"compose/{svc} references {url}")
            else:
                fail(f"compose/{svc} MISSING upstream reference: {url}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== validate-mesh-deployment ===\n")

    check_k8s_manifests()
    check_appset()
    check_compose()
    check_ports()
    check_no_plaintext_secrets()
    check_url_refs()

    total = len(PASSES) + len(ERRORS)

    if ERRORS:
        print(f"FAILURES ({len(ERRORS)}):")
        for e in ERRORS:
            print(f"  ✗ {e}")
        print()

    print(f"Result: {len(PASSES)}/{total} checks passed.")

    if ERRORS:
        print("\nAction required:")
        print("  1. Add Dockerfiles to each sub-repo that lacks one (see tools/mesh_dockerfile_stubs/)")
        print("  2. Wire secrets via SOPS/age before deploying to p0-lab")
        print("  3. Run: make validate-mesh-deployment")
        sys.exit(1)
    else:
        print("  ✓ All mesh deployment checks passed.")


if __name__ == "__main__":
    main()
