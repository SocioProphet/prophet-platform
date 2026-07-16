#!/usr/bin/env python3
"""Run each service's image and assert it honours the chart contract.

The chart states a contract: the container listens on `.Values.service.port` and
answers `.Values.probes.path`, as uid 10001 with a read-only rootfs. That contract
is correct and was, until now, enforced by nobody — so four services violated it
simultaneously and CI stayed green the whole time:

  socioprophet-web  nginx listened on 80, chart probed 8080          574 restarts
  osm-map-api       uvicorn binds 8088, values declared 8080         940 restarts
  agentic-os-api    serves /health, chart probes /healthz            939 restarts
  gateway           serves /health, chart probes /healthz            620 restarts

Every one is a two-line diff. None was findable by reading YAML, because the truth
lives in the image, not the manifest. So: start the container the way Kubernetes
will, and ask it.

This is the difference between a standard and a gate. `docs` say what should be
true; this asks whether it IS.

Usage:
  tools/verify_probe_contract.py --service gateway --image <ref>
  tools/verify_probe_contract.py --all --registry us-central1-docker.pkg.dev/...

Exit 0 = the image honours what the values file promises.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    print("verify_probe_contract: PyYAML required", file=sys.stderr)
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parents[1]
VALUES_DIR = ROOT / "deploy" / "values"
CHART_VALUES = ROOT / "charts" / "socioprophet-service" / "values.yaml"

# Services whose image needs real dependencies (a DB, a backend) to answer a probe
# at all. Their contract is real but not testable by "docker run" alone — asserting
# it here would produce a red build that teaches nothing.
NEEDS_DEPENDENCIES = {
    "api",              # tritRPC core
    "socbase-auth",     # GoTrue runs migrations against Postgres on boot
    "socbase-rest",     # PostgREST refuses to start without a reachable DB
    "gateway",          # /health pings the TriTRPC backend and 502s without it
    "eval-fabric-api",  # ClickHouse
    "reasoning-failure-runner",
}


def runtime() -> str:
    for exe in ("docker", "podman"):
        if subprocess.run(["which", exe], capture_output=True).returncode == 0:
            return exe
    print("verify_probe_contract: need docker or podman", file=sys.stderr)
    raise SystemExit(1)


def chart_defaults() -> dict:
    d = yaml.safe_load(CHART_VALUES.read_text()) or {}
    return {
        "port": ((d.get("service") or {}).get("port")),
        "path": ((d.get("probes") or {}).get("path")),
    }


def contract_for(service: str) -> dict | None:
    """What the values file PROMISES: port + probe path, chart defaults applied."""
    p = VALUES_DIR / f"{service}.yaml"
    if not p.exists():
        return None
    v = yaml.safe_load(p.read_text()) or {}
    defaults = chart_defaults()
    return {
        "port": (v.get("service") or {}).get("port", defaults["port"]),
        "path": (v.get("probes") or {}).get("path", defaults["path"]),
        "repository": (v.get("image") or {}).get("repository"),
        "registry": ((v.get("image") or {}).get("registry") or "").strip(),
    }


def probe(url: str, timeout: float) -> int | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def verify(service: str, image: str, rt: str, wait: int = 45) -> tuple[bool, str]:
    c = contract_for(service)
    if not c:
        return False, f"{service}: no deploy/values/{service}.yaml"
    port, path = c["port"], c["path"]
    name = f"probe-contract-{service}-{int(time.time())}"

    # Run it the way Kubernetes will: non-root uid 10001, read-only rootfs, no caps,
    # writable scratch only where the chart provides emptyDirs. A container that only
    # passes as root proves nothing about how it will actually be scheduled.
    cmd = [
        rt, "run", "-d", "--name", name,
        "--user", "10001:10001", "--read-only", "--cap-drop", "ALL",
        "--tmpfs", "/tmp:rw,mode=1777",
        "--tmpfs", "/var/run:rw,mode=0777",
        "--tmpfs", "/var/cache/nginx:rw,mode=0777",
        "-p", f"{port}", image,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return False, f"{service}: container failed to start: {r.stderr.strip()[:160]}"

    try:
        # Find the host port the runtime mapped.
        pr = subprocess.run([rt, "port", name, str(port)], capture_output=True, text=True)
        m = re.search(r":(\d+)\s*$", pr.stdout.strip().splitlines()[0]) if pr.stdout.strip() else None
        if not m:
            return False, f"{service}: image never published container port {port} — the values file promises it"
        hostport = m.group(1)

        deadline = time.time() + wait
        last = None
        while time.time() < deadline:
            last = probe(f"http://127.0.0.1:{hostport}{path}", 3)
            if last and 200 <= last < 400:
                return True, f"{service}: {path} -> {last} on port {port} — contract honoured"
            time.sleep(1.5)

        logs = subprocess.run([rt, "logs", "--tail", "6", name], capture_output=True, text=True)
        detail = (logs.stdout + logs.stderr).strip().replace("\n", " | ")[:200]
        if last is None:
            return False, (
                f"{service}: NOTHING listening on port {port} within {wait}s — the values file "
                f"promises service.port={port}. This is the osm-map-api bug (bound 8088, "
                f"declared 8080). Container said: {detail}"
            )
        return False, (
            f"{service}: port {port} answers but {path} -> {last} — the chart probes this path "
            f"and a non-2xx means the kubelet will kill it on a loop. This is the agentic-os-api "
            f"bug (serves /health, chart probes /healthz). Container said: {detail}"
        )
    finally:
        subprocess.run([rt, "rm", "-f", name], capture_output=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--service")
    ap.add_argument("--image")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--registry", default="us-central1-docker.pkg.dev/socioprophet-platform/socioprophet")
    ap.add_argument("--tag", default="latest")
    args = ap.parse_args()
    rt = runtime()

    if args.service and args.image:
        ok, msg = verify(args.service, args.image, rt)
        print(("OK: " if ok else "FAIL: ") + msg)
        return 0 if ok else 1

    if not args.all:
        ap.print_help()
        return 2

    failures = 0
    for p in sorted(VALUES_DIR.glob("*.yaml")):
        service = p.stem
        c = contract_for(service)
        if not c or not c["repository"]:
            continue
        if service in NEEDS_DEPENDENCIES:
            print(f"SKIP: {service} — needs live dependencies to answer a probe (see NEEDS_DEPENDENCIES)")
            continue
        registry = c["registry"] or args.registry
        image = f"{registry}/{c['repository']}:{args.tag}"
        ok, msg = verify(service, image, rt)
        print(("OK: " if ok else "FAIL: ") + msg)
        failures += 0 if ok else 1

    print(f"\nprobe-contract: {failures} violation(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
