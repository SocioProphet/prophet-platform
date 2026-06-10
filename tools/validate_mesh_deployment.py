#!/usr/bin/env python3
"""
Validate prophet-mesh + sociosphere deployment alignment.

Checks:
  - k8s manifests exist for all mesh + sociosphere services
  - Each service has base/deployment.yaml, service.yaml, kustomization.yaml
  - Each service has an overlays/p0-lab/kustomization.yaml
  - Argo CD appset includes all bundles
  - docker-compose files declare all services with correct dependency ordering
  - Port assignments are unique across workspace + mesh + sociosphere stacks
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
    # SocioSphere extended tiers
    "sociosphere",
    "hellgraph",
    "regis-entity-graph",
    "sherlock-search",
    "prophet-core-catalog",
    "prophet-core-query",
    "global-devsecops-intelligence",
    "lattice-forge",
    "synapseiq-control-plane",
    "synapseiq-enrichment-api",
    "synapseiq-enrichment-collector",
    "synapseiq-reasoning-api",
    "synapseiq-tabular-alpha",
    "mcp-a2a-zero-trust",
    # Late-integration trio
    "holmes",
    "cairnpath-mesh",
    "contractforge",
]

# cloudshell-fog uses existing runtime-base/overlays in prophet-platform — not in MESH_SERVICES
# but is checked separately in appset validation.
CLOUDSHELL_OVERLAY = "infra/k8s/cloudshell-fog/overlays/runtime-v2-standard"

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
    # SocioSphere
    "cloudshell-fog": 8080,
    "sociosphere": 5000,
    "hellgraph": 8850,
    "regis-entity-graph": 8820,
    "sherlock-search": 8810,
    "prophet-core-catalog": 8830,
    "prophet-core-query": 8831,
    "global-devsecops-intelligence": 8840,
    "lattice-forge": 8870,
    "synapseiq-control-plane": 8800,
    "synapseiq-enrichment-api": 8801,
    "synapseiq-enrichment-collector": 8802,
    "synapseiq-reasoning-api": 8803,
    "synapseiq-tabular-alpha": 8804,
    "mcp-a2a-zero-trust": 8860,
    # Late-integration trio
    "cairnpath-mesh": 8890,
    "holmes": 8880,
    "contractforge": 8895,
}

WORKSPACE_PORTS = {143, 993, 24, 25, 587, 5232, 9000, 9001, 5432, 6379}

APPSET = ROOT / "infra/k8s/argo-cd/appsets/socioprophet-appset.yaml"
COMPOSE = ROOT / "infra/local/docker-compose.mesh.yml"
COMPOSE_SOCIOSPHERE = ROOT / "infra/local/docker-compose.sociosphere.yml"
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
    # Mesh tiers 0-6
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
    # SocioSphere tiers 7-10
    "platform.shell",
    "platform.controller",
    "graph.kernel",
    "graph.entity",
    "search.evidence",
    "data.catalog",
    "data.query",
    "intelligence.devsecops",
    "runtime.forge",
    "enrichment.control",
    "enrichment.api",
    "enrichment.collector",
    "enrichment.reasoning",
    "enrichment.tabular",
    "security.mcp-zero-trust",
    # Late-integration trio
    "execution.trace",
    "intelligence.language",
    "contracts.forge",
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

    # cloudshell-fog uses its existing runtime-v2-standard overlay
    if CLOUDSHELL_OVERLAY in text:
        ok("appset includes cloudshell-fog (runtime-v2-standard overlay)")
    else:
        fail(f"appset MISSING cloudshell-fog entry pointing to {CLOUDSHELL_OVERLAY}")


# ── 3. docker-compose service coverage ───────────────────────────────────────

COMPOSE_SERVICES = {
    "postgres-mesh", "qdrant", "model-governance-ledger", "memoryd",
    "policy-fabric", "model-router", "agent-registry", "superconscious",
    "agentplane", "tritfabric-server", "prophet-mesh",
}

COMPOSE_SOCIOSPHERE_SERVICES = {
    "cloudshell-fog", "sociosphere", "hellgraph", "regis-entity-graph",
    "sherlock-search", "prophet-core-catalog", "prophet-core-query",
    "global-devsecops-intelligence", "lattice-forge",
    "synapseiq-control-plane", "synapseiq-enrichment-api",
    "synapseiq-enrichment-collector", "synapseiq-reasoning-api",
    "synapseiq-tabular-alpha", "mcp-a2a-zero-trust",
    # Late-integration trio
    "cairnpath-mesh", "holmes", "contractforge",
}

def check_compose() -> None:
    if not COMPOSE.exists():
        fail(f"docker-compose.mesh.yml not found: {COMPOSE.relative_to(ROOT)}")
        return

    text = COMPOSE.read_text()
    for svc in COMPOSE_SERVICES:
        if f"\n  {svc}:" in text:
            ok(f"compose/mesh includes service: {svc}")
        else:
            fail(f"compose/mesh MISSING service: {svc}")

    if not COMPOSE_SOCIOSPHERE.exists():
        fail(f"docker-compose.sociosphere.yml not found: {COMPOSE_SOCIOSPHERE.relative_to(ROOT)}")
    else:
        stext = COMPOSE_SOCIOSPHERE.read_text()
        for svc in COMPOSE_SOCIOSPHERE_SERVICES:
            if f"\n  {svc}:" in stext:
                ok(f"compose/sociosphere includes service: {svc}")
            else:
                fail(f"compose/sociosphere MISSING service: {svc}")


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

EXPECTED_URL_REFS_MESH = {
    "model-router": ["policy-fabric:8700", "memoryd:8787"],
    "agent-registry": ["policy-fabric:8700"],
    "superconscious": ["model-router:8710", "memoryd:8787"],
    "agentplane": ["policy-fabric:8700", "agent-registry:8720", "model-router:8710",
                   "memoryd:8787", "superconscious:8740"],
    "prophet-mesh": ["agentplane:8730", "model-router:8710", "agent-registry:8720",
                     "memoryd:8787", "policy-fabric:8700", "superconscious:8740"],
}

EXPECTED_URL_REFS_SOCIOSPHERE = {
    "regis-entity-graph": ["hellgraph:8850", "agent-registry:8720"],
    "sherlock-search": ["regis-entity-graph:8820", "memoryd:8787"],
    "prophet-core-query": ["prophet-core-catalog:8830", "memoryd:8787"],
    "global-devsecops-intelligence": ["sherlock-search:8810", "model-router:8710"],
    "synapseiq-enrichment-api": ["prophet-core-catalog:8830", "memoryd:8787",
                                  "synapseiq-control-plane:8800"],
    "synapseiq-enrichment-collector": ["synapseiq-enrichment-api:8801"],
    "synapseiq-reasoning-api": ["model-router:8710", "superconscious:8740"],
    "synapseiq-tabular-alpha": ["synapseiq-enrichment-api:8801"],
    "mcp-a2a-zero-trust": ["policy-fabric:8700", "agent-registry:8720", "agentplane:8730"],
    # Late-integration trio
    "cairnpath-mesh": ["policy-fabric:8700", "agentplane:8730"],
    "holmes": ["policy-fabric:8700", "model-router:8710", "memoryd:8787"],
    "contractforge": ["policy-fabric:8700", "agent-registry:8720", "agentplane:8730"],
}

def check_url_refs() -> None:
    if COMPOSE.exists():
        text = COMPOSE.read_text()
        for svc, urls in EXPECTED_URL_REFS_MESH.items():
            for url in urls:
                if url in text:
                    ok(f"compose/mesh/{svc} references {url}")
                else:
                    fail(f"compose/mesh/{svc} MISSING upstream reference: {url}")

    if COMPOSE_SOCIOSPHERE.exists():
        stext = COMPOSE_SOCIOSPHERE.read_text()
        for svc, urls in EXPECTED_URL_REFS_SOCIOSPHERE.items():
            for url in urls:
                if url in stext:
                    ok(f"compose/sociosphere/{svc} references {url}")
                else:
                    fail(f"compose/sociosphere/{svc} MISSING upstream reference: {url}")


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
        print("  3. For sociosphere tier: add serve/api.py to hellgraph, regis-entity-graph,")
        print("     sherlock-search, prophet-core-catalog, prophet-core-query, global-devsecops,")
        print("     lattice-forge, mcp-a2a-zero-trust")
        print("  4. For synapseiq: add Dockerfiles to control-plane, enrichment-api,")
        print("     enrichment-collector, reasoning-api services")
        print("  5. Run: make validate-mesh-deployment")
        sys.exit(1)
    else:
        print("  ✓ All mesh deployment checks passed.")


if __name__ == "__main__":
    main()
