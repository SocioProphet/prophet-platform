from mount_intent import (
    EGRESSABLE_INTENTS,
    ArtifactState,
    Layer,
    MountDeclaration,
    MountIntent,
    PolicyDecision,
    Retention,
    Runtime,
    can_transition,
    is_terminal,
    may_cache,
    may_delete,
    may_egress,
    resolve,
    transition,
)
import pytest


# ── the core sovereignty invariant: only canonical + curated may egress ─────────────────────
def test_only_canonical_and_curated_may_egress():
    assert EGRESSABLE_INTENTS == {MountIntent.CANONICAL_DATA, MountIntent.CURATED_CORPUS}


@pytest.mark.parametrize(
    "intent",
    [MountIntent.DERIVED_INDEX, MountIntent.SCRATCH, MountIntent.CACHE,
     MountIntent.SECRETS, MountIntent.CONFIG_RO, MountIntent.IPC_BRIDGE],
)
def test_sensitive_and_rebuildable_never_egress(intent):
    assert may_egress(intent) is False


def test_secrets_never_egress_or_cache():
    assert may_egress(MountIntent.SECRETS) is False
    assert may_cache(MountIntent.SECRETS) is False


# ── every intent resolves to a real backend on every runtime ────────────────────────────────
@pytest.mark.parametrize("runtime", list(Runtime))
@pytest.mark.parametrize("intent", list(MountIntent))
def test_resolve_covers_every_intent_runtime(intent, runtime):
    spec = resolve(intent, runtime)
    assert spec["backend"]["kind"]
    assert spec["policy"]["may_egress"] == may_egress(intent)
    assert spec["layer"] in {l.value for l in Layer}


def test_derived_index_is_rebuildable_and_collectable():
    assert resolve(MountIntent.DERIVED_INDEX, Runtime.PODMAN)["retention"] == Retention.REBUILDABLE.value
    assert may_delete(MountIntent.DERIVED_INDEX) is True


def test_canonical_is_durable_and_retention_gated():
    assert may_delete(MountIntent.CANONICAL_DATA) is False  # deletion is retention-gated


def test_podman_cache_uses_overlay():
    assert resolve(MountIntent.CACHE, Runtime.PODMAN)["backend"] == {"kind": "overlay", "options": ":O"}


# ── policy decisions are auditable ──────────────────────────────────────────────────────────
def test_policy_decision_egress_is_auditable():
    d = PolicyDecision.egress(MountIntent.SECRETS)
    assert d.gate == "egress" and d.allowed is False and d.decided_at
    assert PolicyDecision.egress(MountIntent.CANONICAL_DATA).allowed is True
    assert PolicyDecision.deletion(MountIntent.CANONICAL_DATA).allowed is False


def test_mount_declaration_resolves():
    decl = MountDeclaration(name="store", intent=MountIntent.CANONICAL_DATA, mount_path="/store")
    r = decl.resolved(Runtime.KUBERNETES)
    assert r["backend"]["kind"] == "persistentVolumeClaim" and r["mount_path"] == "/store"


# ── lifecycle state machine ─────────────────────────────────────────────────────────────────
def test_happy_path_transitions():
    s = ArtifactState.INGESTED_RAW
    for nxt in (ArtifactState.NORMALIZED, ArtifactState.EXTRACTED, ArtifactState.INDEXED, ArtifactState.SERVED):
        s = transition(s, nxt)
    assert s == ArtifactState.SERVED


def test_legal_hold_blocks_deletion():
    with pytest.raises(ValueError, match="deletion blocked"):
        transition(ArtifactState.LEGAL_HOLD, ArtifactState.DELETED)  # must be released first
    # released path is allowed
    assert transition(ArtifactState.LEGAL_HOLD, ArtifactState.SERVED) == ArtifactState.SERVED


def test_illegal_transition_rejected():
    with pytest.raises(ValueError, match="illegal artifact transition"):
        transition(ArtifactState.INGESTED_RAW, ArtifactState.SERVED)


def test_vendor_cache_rematerializes():
    assert can_transition(ArtifactState.EXPIRED_VENDOR_CACHE, ArtifactState.SERVED)
    assert is_terminal(ArtifactState.DELETED)
