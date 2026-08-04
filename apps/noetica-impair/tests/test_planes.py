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


# ── weight staging (the piece that made a GPU run possible at all) ───────────

def test_no_staging_when_no_repos_requested():
    from noetica_impair.planes.gcp_vm import GCPVMPlane
    assert GCPVMPlane()._staging_script() == ""


def test_staging_reads_the_token_from_secret_manager_not_metadata():
    """Instance metadata is readable by anyone with compute.instances.get."""
    from noetica_impair.planes.gcp_vm import GCPVMPlane
    sc = GCPVMPlane(stage_repos=("google/gemma-2-9b-it",))._staging_script()
    assert "gcloud secrets versions access latest" in sc
    assert "metadata.google.internal" not in sc, "the token must not ride in metadata"


def test_a_failed_stage_aborts_rather_than_running_without_weights():
    """A run that finds no weights and proceeds burns the whole VM budget producing
    nothing, and the empty result looks like a successful run."""
    from noetica_impair.planes.gcp_vm import GCPVMPlane
    sc = GCPVMPlane(stage_repos=("google/gemma-2-9b-it",))._staging_script()
    assert "exit 91" in sc and "exit 93" in sc
    assert "FATAL" in sc


def test_includes_are_per_repo_so_a_657gb_sae_suite_is_not_pulled_whole():
    from noetica_impair.planes.gcp_vm import GCPVMPlane
    pl = GCPVMPlane(
        stage_repos=("google/gemma-scope-9b-pt-res",),
        stage_includes=(("google/gemma-scope-9b-pt-res", "layer_20/width_16k/*/params.npz"),),
    )
    sc = pl._staging_script()
    assert "--include" in sc and "layer_20" in sc


def test_the_container_still_runs_offline_with_weights_mounted_readonly():
    """Invariant 0.6: the RIG never fetches. Staging happens on the VM, explicitly."""
    from noetica_impair.planes.base import RunJob
    from noetica_impair.planes.gcp_vm import GCPVMPlane
    sc = GCPVMPlane(stage_repos=("google/gemma-2-9b-it",)).startup_script(
        RunJob(model_key="gemma2-9b", substance="ALCOHOL", doses=(0.0, 0.6), seed=1))
    assert "-v /var/impair/weights:/weights:ro" in sc, "weights mount must be read-only"
    assert "-e IMPAIR_WEIGHTS=/weights" in sc


def test_staging_runs_before_the_container():
    from noetica_impair.planes.base import RunJob
    from noetica_impair.planes.gcp_vm import GCPVMPlane
    sc = GCPVMPlane(stage_repos=("google/gemma-2-9b-it",)).startup_script(
        RunJob(model_key="gemma2-9b", substance="ALCOHOL", doses=(0.0, 0.6), seed=1))
    # "$RUNTIME run" now, not "docker run" — the plane is runtime-agnostic.
    assert sc.index("hf download") < sc.index("$RUNTIME run"), "weights must exist first"


def test_gpu_maintenance_policy_is_set_for_bundled_accelerators_too():
    """g2/a2 bundle their GPU and take no --accelerator flag. The policy used to be
    attached to that flag's branch, so a g2 create kept the default MIGRATE and the API
    rejected it outright. Every GPU machine needs TERMINATE, flag or not."""
    from noetica_impair.planes.base import RunJob
    from noetica_impair.planes.gcp_vm import GCPVMPlane
    job = RunJob(model_key="gemma2-9b", doses=(0.0,), seed=1, non_sweep=True)
    for mt in ("g2-standard-8",):
        cmd = GCPVMPlane(machine_type=mt).create_command(job)
        assert "--maintenance-policy=TERMINATE" in cmd, f"{mt} must terminate on maintenance"
        assert cmd.count("--maintenance-policy=TERMINATE") == 1, "set exactly once"


def test_preflight_checks_docker_before_staging_weights():
    """Discovering docker is missing AFTER pulling 18.5GB wastes the whole download.
    Both preflight checks sit next to the GPU check, before any staging."""
    from noetica_impair.planes.base import RunJob
    from noetica_impair.planes.gcp_vm import GCPVMPlane
    sc = GCPVMPlane(stage_repos=("google/gemma-2-9b-it",)).startup_script(
        RunJob(model_key="gemma2-9b", doses=(0.0,), seed=1, non_sweep=True))
    assert sc.index("command -v docker") < sc.index("hf download")
    assert sc.index("nvidia-smi") < sc.index("hf download")


def test_staging_does_not_assume_a_bare_pip_on_path():
    """The accelerator image ships python3 but not pip; the first real launch died on
    `pip: command not found` after reaching the staging step."""
    from noetica_impair.planes.gcp_vm import GCPVMPlane
    sc = GCPVMPlane(stage_repos=("google/gemma-2-9b-it",))._staging_script()
    assert "python3 -m pip" in sc
    assert "python3-pip" in sc, "must install pip when absent"
    import re
    # A BARE `pip install` -- one not preceded by `-m ` -- is what died on the image.
    # The earlier pattern used a \w lookbehind, which a SPACE satisfies, so it flagged
    # the correct `python3 -m pip install` too.
    assert not re.search(r"(?<!-m )pip install", sc), "use python3 -m pip, not bare pip"


def test_snap_bin_is_on_path_before_any_gcloud_call():
    """A metadata startup-script gets a minimal PATH without /snap/bin. On the Ubuntu
    accelerator image gcloud and gsutil ARE snaps, so without this the secrets read
    returned empty (staging aborted) and the log upload silently failed — which is why
    the first failed runs left nothing in GCS to debug from."""
    from noetica_impair.planes.base import RunJob
    from noetica_impair.planes.gcp_vm import GCPVMPlane
    sc = GCPVMPlane(stage_repos=("google/gemma-2-9b-it",)).startup_script(
        RunJob(model_key="gemma2-9b", doses=(0.0,), seed=1, non_sweep=True))
    # Strip comment lines first: the script DOCUMENTS why it needs /snap/bin, and
    # matching that prose would fail the test for explaining itself -- the same trap
    # this suite hit once already.
    code = "\n".join(l for l in sc.splitlines() if not l.lstrip().startswith("#"))
    assert "/snap/bin" in code
    assert code.index("export PATH=") < code.index("gcloud secrets"), "PATH must precede use"
    assert code.index("export PATH=") < code.index("cleanup()"), "cleanup needs it too"


def test_self_delete_trap_is_registered_before_anything_that_can_fail():
    """THE expensive failure mode. An abort above the trap (an unbound $HOME under
    `set -u`) once left a GPU instance RUNNING with no work and no self-delete. A
    self-deleting VM whose self-delete registers late is not self-deleting."""
    from noetica_impair.planes.base import RunJob
    from noetica_impair.planes.gcp_vm import GCPVMPlane
    sc = GCPVMPlane(stage_repos=("google/gemma-2-9b-it",)).startup_script(
        RunJob(model_key="gemma2-9b", doses=(0.0,), seed=1, non_sweep=True))
    code = "\n".join(l for l in sc.splitlines() if not l.lstrip().startswith("#"))
    trap = code.index("trap cleanup EXIT")
    for fallible in ("nvidia-smi", "gcloud secrets", "hf download", "docker run",
                     "apt-get", "python3 -m pip"):
        i = code.find(fallible)
        if i > 0:
            assert trap < i, f"trap must precede {fallible!r} or a failure strands the VM"


def test_no_unguarded_HOME_under_set_u():
    """`set -u` plus an unset HOME aborts the script instantly. A metadata
    startup-script runs as root, where HOME is frequently unset."""
    import re
    from noetica_impair.planes.base import RunJob
    from noetica_impair.planes.gcp_vm import GCPVMPlane
    sc = GCPVMPlane(stage_repos=("google/gemma-2-9b-it",)).startup_script(
        RunJob(model_key="gemma2-9b", doses=(0.0,), seed=1, non_sweep=True))
    code = "\n".join(l for l in sc.splitlines() if not l.lstrip().startswith("#"))
    assert not re.search(r"(?<!\{)\$HOME(?!:-)", code), "use ${HOME:-/root}"


def test_container_runtime_is_docker_or_podman_not_hardcoded():
    """The estate is podman-first on workstations; sourceos-continuum's
    scripts/dev_up.sh::need_runtime() prefers docker then falls back to podman. This
    plane hardcoded docker, which made it the odd one out."""
    from noetica_impair.planes.base import RunJob
    from noetica_impair.planes.gcp_vm import GCPVMPlane
    sc = GCPVMPlane(stage_repos=("google/gemma-2-9b-it",)).startup_script(
        RunJob(model_key="gemma2-9b", doses=(0.0,), seed=1, non_sweep=True))
    code = "\n".join(l for l in sc.splitlines() if not l.lstrip().startswith("#"))
    assert "command -v podman" in code, "podman must be a supported runtime"
    assert "$RUNTIME run" in code, "the run must use the detected runtime"
    assert "docker run " not in code, "no hardcoded docker invocation"


def test_registry_login_happens_before_the_pull():
    """Artifact Registry needs an explicit credential helper; without it the pull fails
    with exit 125, which reads as a generic runtime error and says nothing about auth."""
    from noetica_impair.planes.base import RunJob
    from noetica_impair.planes.gcp_vm import GCPVMPlane
    sc = GCPVMPlane(stage_repos=("google/gemma-2-9b-it",)).startup_script(
        RunJob(model_key="gemma2-9b", doses=(0.0,), seed=1, non_sweep=True))
    code = "\n".join(l for l in sc.splitlines() if not l.lstrip().startswith("#"))
    assert code.index("oauth2accesstoken") < code.index("$RUNTIME run")
