"""The directional + verified-immutable + link-aware defaults, enforced by construction."""
import pytest

from mount_intent import (
    Direction,
    LinkAvailability,
    MountDeclaration,
    MountIntent,
    Runtime,
    WorkloadDeclaration,
    check_single_egress,
    direction,
    resolve,
    tenant_scoped_source,
    verified_immutable,
)


# ── direction axis ──────────────────────────────────────────────────────────────────────
def test_canonical_is_the_only_egress_direction():
    egress = {i for i in MountIntent if direction(i) in (Direction.EGRESS, Direction.BIDIRECTIONAL)}
    assert egress == {MountIntent.CANONICAL_DATA}  # a single durable-write chokepoint


@pytest.mark.parametrize("intent", [MountIntent.CURATED_CORPUS, MountIntent.CONFIG_RO, MountIntent.SECRETS])
def test_read_only_inputs_are_ingress(intent):
    assert direction(intent) == Direction.INGRESS


@pytest.mark.parametrize("intent", [MountIntent.SCRATCH, MountIntent.CACHE, MountIntent.DERIVED_INDEX, MountIntent.IPC_BRIDGE])
def test_node_local_intents_are_none(intent):
    assert direction(intent) == Direction.NONE


# ── single-egress-chokepoint invariant ──────────────────────────────────────────────────
def test_one_egress_is_allowed():
    assert check_single_egress([MountIntent.CANONICAL_DATA, MountIntent.CURATED_CORPUS,
                                MountIntent.SCRATCH]) == []


def test_two_egress_is_a_violation():
    # only one intent is egress-direction, so a genuine 2-egress set needs it twice — the
    # workload-level check counts declared egress mounts, which the WorkloadDeclaration builds.
    v = check_single_egress([MountIntent.CANONICAL_DATA, MountIntent.CANONICAL_DATA])
    assert v and "at most one" in v[0]


def test_workload_rejects_two_egress_mounts():
    with pytest.raises(ValueError, match="at most one"):
        WorkloadDeclaration(name="w", mounts=[
            MountDeclaration(name="a", intent=MountIntent.CANONICAL_DATA, mount_path="/a"),
            MountDeclaration(name="b", intent=MountIntent.CANONICAL_DATA, mount_path="/b"),
        ])


def test_workload_accepts_one_egress_plus_ingress():
    w = WorkloadDeclaration(name="w", mounts=[
        MountDeclaration(name="out", intent=MountIntent.CANONICAL_DATA, mount_path="/out"),
        MountDeclaration(name="corpus", intent=MountIntent.CURATED_CORPUS, mount_path="/corpus",
                         verity_root_hash="a" * 64),
        MountDeclaration(name="tmp", intent=MountIntent.SCRATCH, mount_path="/tmp"),
    ])
    assert len(w.mounts) == 3


# ── verified-immutable corpus: verity root hash is mandatory ─────────────────────────────
def test_curated_corpus_is_verified_immutable():
    assert verified_immutable(MountIntent.CURATED_CORPUS) is True
    r = resolve(MountIntent.CURATED_CORPUS, Runtime.PODMAN)
    assert r["verified_immutable"] is True and r["requires_verity_root_hash"] is True
    assert r["backend"]["kind"] == "image"  # the type=image / squashfs+dm-verity backend


def test_curated_corpus_requires_pinned_verity_hash():
    with pytest.raises(ValueError, match="verity_root_hash"):
        MountDeclaration(name="c", intent=MountIntent.CURATED_CORPUS, mount_path="/c")
    # a valid 64-hex hash is accepted
    ok = MountDeclaration(name="c", intent=MountIntent.CURATED_CORPUS, mount_path="/c",
                          verity_root_hash="f" * 64)
    assert ok.resolved(Runtime.PODMAN)["verity_root_hash"] == "f" * 64


def test_non_verified_intent_rejects_stray_verity_hash():
    with pytest.raises(ValueError, match="meaningless"):
        MountDeclaration(name="s", intent=MountIntent.SCRATCH, mount_path="/s",
                         verity_root_hash="a" * 64)


# ── link-aware sync semantics: reference vs copy ─────────────────────────────────────────
def test_egress_over_reliable_link_is_reference_no_reconciliation():
    r = resolve(MountIntent.CANONICAL_DATA, Runtime.KUBERNETES, LinkAvailability.RELIABLE)
    assert r["sync_semantics"] == "reference"
    assert r["requires_conflict_resolution"] is False


def test_egress_over_intermittent_link_forces_copy_and_reconciliation():
    r = resolve(MountIntent.CANONICAL_DATA, Runtime.KUBERNETES, LinkAvailability.INTERMITTENT)
    assert r["sync_semantics"] == "copy"
    assert r["requires_conflict_resolution"] is True  # SP-EVAL-CRF-001 only here


def test_node_local_never_needs_reconciliation():
    for intent in (MountIntent.DERIVED_INDEX, MountIntent.SCRATCH, MountIntent.CACHE):
        r = resolve(intent, Runtime.PODMAN, LinkAvailability.INTERMITTENT)
        assert r["sync_semantics"] == "node_local" and r["requires_conflict_resolution"] is False


# ── construction-enforced tenancy ────────────────────────────────────────────────────────
def test_canonical_binds_tenancy_in_source():
    assert resolve(MountIntent.CANONICAL_DATA, Runtime.KUBERNETES)["tenancy_in_source"] is True


def test_tenant_scoped_source_is_constructed():
    assert tenant_scoped_source("rclone-filestore", "sess_013Sxj", "/mnt/out") \
        == "rclone-filestore:sess_013Sxj:/mnt/out"
    with pytest.raises(ValueError):
        tenant_scoped_source("store", "  ", "/p")  # empty tenant is refused
