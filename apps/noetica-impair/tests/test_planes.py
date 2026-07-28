"""Planes render correct submission artifacts without executing anything."""

from __future__ import annotations

import pytest
import yaml

from noetica_impair import planes
from noetica_impair.planes import RunJob
from noetica_impair.planes.gcp_vm import ACCELERATORS, GCPVMPlane
from noetica_impair.planes.gke import GKEPlane


def job(**kw) -> RunJob:
    kw.setdefault("model_key", "gemma2-9b")
    kw.setdefault("substance", "ALCOHOL")
    return RunJob(**kw)


def test_runjob_requires_exactly_one_driver():
    with pytest.raises(ValueError, match="exactly one driver"):
        RunJob(model_key="gemma2-9b")                       # neither
    with pytest.raises(ValueError, match="exactly one driver"):
        RunJob(model_key="gemma2-9b", substance="ALCOHOL", topical_stimulus="gematria")


def test_gke_manifest_requests_a_gpu():
    m = GKEPlane().manifest(job())
    c = m["spec"]["template"]["spec"]["containers"][0]
    assert c["resources"]["limits"]["nvidia.com/gpu"] == "1"
    sel = m["spec"]["template"]["spec"]["nodeSelector"]
    assert sel["cloud.google.com/gke-accelerator"] == "nvidia-l4"
    assert m["spec"]["template"]["spec"]["tolerations"][0]["key"] == "nvidia.com/gpu"


def test_gke_manifest_mounts_writable_cache():
    """The platform's baseline is readOnlyRootFilesystem; HF needs somewhere to write."""
    m = GKEPlane().manifest(job())
    spec = m["spec"]["template"]["spec"]
    mounts = {v["mountPath"] for v in spec["containers"][0]["volumeMounts"]}
    assert {"/cache", "/tmp"} <= mounts
    env = {e["name"]: e["value"] for e in spec["containers"][0]["env"]}
    assert env["HF_HOME"].startswith("/cache")
    assert env["HF_HUB_OFFLINE"] == "1", "remote runs must not reach the hub"


def test_gke_plan_is_valid_yaml_and_not_submitted():
    h = GKEPlane().plan(job())
    assert not h.submitted
    parsed = yaml.safe_load(h.artifact)
    assert parsed["kind"] == "Job"


def test_gcp_vm_l4_takes_no_accelerator_flag():
    """g2-standard-8 bundles the L4; passing --accelerator is an error."""
    cmd = GCPVMPlane(machine_type="g2-standard-8").create_command(job())
    assert not any(c.startswith("--accelerator") for c in cmd)
    assert ACCELERATORS["g2-standard-8"][0] is None


def test_gcp_vm_t4_requires_accelerator_flag():
    cmd = GCPVMPlane(machine_type="n1-standard-8").create_command(job())
    assert any(c.startswith("--accelerator=type=nvidia-tesla-t4") for c in cmd)


def test_gcp_vm_unknown_machine_type_rejected():
    with pytest.raises(ValueError, match="unknown machine type"):
        GCPVMPlane(machine_type="made-up").create_command(job())


def test_gcp_vm_self_deletes_and_uploads_before_teardown():
    script = GCPVMPlane().startup_script(job())
    assert "trap cleanup EXIT" in script
    assert "instances delete" in script
    # Upload must precede deletion inside cleanup, or receipts die with the box.
    assert script.index("gsutil -m cp") < script.index("instances delete")
    assert "nvidia-smi" in script, "must fail loudly rather than fall back to CPU"


def test_job_name_is_k8s_safe():
    j = job(model_key="mixtral-8x7b", substance="ALCOHOL_MOE", seed=3)
    assert j.name.islower() and "_" not in j.name


def test_registry_exposes_all_planes():
    assert set(planes.PLANES) == {"local", "gke", "gcp-vm"}
    assert planes.get("local").name == "local"
