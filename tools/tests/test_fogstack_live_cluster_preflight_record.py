from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("tools/emit_fogstack_live_cluster_preflight_record.py")


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def run_preflight(output: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), "--output", str(output), *extra], capture_output=True, text=True)


def fake_kubectl(path: Path, log_path: Path) -> Path:
    script = f'''#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

log_path = Path({str(log_path)!r})
args = sys.argv[1:]
log_path.parent.mkdir(parents=True, exist_ok=True)
with log_path.open("a", encoding="utf-8") as handle:
    handle.write(" ".join(args) + "\\n")

if args[:2] == ["config", "current-context"]:
    print("kind-fogstack")
    raise SystemExit(0)
if args[:2] == ["version", "--client"]:
    print(json.dumps({{"clientVersion": {{"gitVersion": "v1.30.0"}}}}))
    raise SystemExit(0)
if args[:1] == ["cluster-info"]:
    print("Kubernetes control plane is running at https://127.0.0.1")
    raise SystemExit(0)
if args[:2] == ["get", "namespace"]:
    print(json.dumps({{"metadata": {{"name": args[2], "labels": {{"fogstack.socioprophet.io/preflight": "true"}}}}}}))
    raise SystemExit(0)
if args[:2] == ["get", "storageclass"]:
    print(json.dumps({{"items": [{{"metadata": {{"name": "topolvm-provisioner"}}, "provisioner": "topolvm.io"}}]}}))
    raise SystemExit(0)
if args[:1] == ["api-resources"]:
    print("pods\\ndeployments.apps\\napplications.argoproj.io\\nkustomizations.kustomize.toolkit.fluxcd.io")
    raise SystemExit(0)
if args[:2] == ["auth", "can-i"]:
    print("yes")
    raise SystemExit(0)
print("unexpected args: " + " ".join(args), file=sys.stderr)
raise SystemExit(2)
'''
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def test_preflight_blocks_safely_when_kubectl_missing(tmp_path: Path) -> None:
    output = tmp_path / "preflight.json"
    proc = run_preflight(output, "--kubectl", "missing-kubectl-for-live-preflight")
    assert proc.returncode == 0
    record = read_json(output)
    assert record["kind"] == "FogStackLiveClusterPreflightRecord"
    assert record["status"] == "blocked"
    assert record["safety"]["mutation_mode"] == "read-only"
    assert record["safety"]["mutated_cluster"] is False
    assert record["safety"]["live_apply_allowed"] is False
    assert record["errors"] == []


def test_preflight_requires_live_cluster_when_requested(tmp_path: Path) -> None:
    output = tmp_path / "preflight.json"
    proc = run_preflight(output, "--kubectl", "missing-kubectl-for-live-preflight", "--require-live-cluster")
    assert proc.returncode == 1
    record = read_json(output)
    assert record["status"] == "blocked"
    assert record["errors"] == ["kubectl unavailable; live cluster preflight not attempted"]


def test_preflight_passes_with_fake_readonly_cluster(tmp_path: Path) -> None:
    output = tmp_path / "preflight.json"
    log_path = tmp_path / "kubectl.log"
    kubectl = fake_kubectl(tmp_path / "kubectl", log_path)
    proc = run_preflight(output, "--kubectl", str(kubectl), "--namespace", "fogstack-access")
    assert proc.returncode == 0, proc.stderr
    record = read_json(output)
    assert record["status"] == "passed"
    assert record["namespace"] == "fogstack-access"
    assert record["safety"]["mutation_mode"] == "read-only"
    assert record["safety"]["mutated_cluster"] is False
    assert record["safety"]["applied_resources"] is False
    assert record["cluster"]["storage"]["topolvm_observed"] is True
    assert record["cluster"]["api_resources"]["gitops_controller_api_observed"] is True
    assert record["cluster"]["authorization"]["can_get_pods"] is True
    assert record["cluster"]["authorization"]["mutation_permissions_observed_by_sar_only"] is True
    assert {check["status"] for check in record["checks"]} == {"passed"}

    calls = log_path.read_text(encoding="utf-8").splitlines()
    forbidden = ("apply", "create", "delete", "patch", "replace", "rollout", "scale", "set", "annotate", "label")
    for call in calls:
        parts = call.split()
        assert parts[0] not in forbidden
    assert "auth can-i create deployments --namespace fogstack-access" in calls
    assert "auth can-i patch deployments --namespace fogstack-access" in calls


def test_preflight_command_allowlist_denies_mutating_family() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("preflight", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.command_is_allowed(["get", "namespace", "fogstack-access"])
    assert module.command_is_allowed(["auth", "can-i", "create", "deployments"])
    assert not module.command_is_allowed(["apply", "-f", "manifests"])
    assert not module.command_is_allowed(["delete", "namespace", "fogstack-access"])
