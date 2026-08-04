"""Mount intent → backend + retention/egress policy.

Storage in the platform is declared by INTENT (what the data means), not by mechanism
(how it is mounted). The intent determines three things by construction:

  1. the backend mount for the target container runtime (K8s / Docker / Podman-rootful),
  2. the store LAYER it belongs to, and
  3. the retention/egress/caching POLICY that governs whether it may ever leave the device.

This encodes the layered store model (diagram: Layer 1 Canonical Object Store → Layer 2 Derived
Stores [disposable, rebuildable] → Layer 3 Vendor Cache [TTL/GC] → Layer 6 Tool Runtime
[ephemeral]) and the Policy Engine that gates egress / caching / deletion. It is the storage-side
counterpart to the ER plane's egress-masking / fog-scope discipline (apps/regis-acr-api): the same
principle — sensitive data never leaves the device unless explicitly, policy-permitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MountIntent(str, Enum):
    """What a mounted path MEANS. The only vocabulary workloads should declare."""

    CANONICAL_DATA = "canonical_data"   # source of truth (person-graph, canon)
    CURATED_CORPUS = "curated_corpus"   # segmented commons (OCW/academy), durable + cacheable
    DERIVED_INDEX = "derived_index"     # chunks/keyword/vectors — rebuildable from canonical
    SCRATCH = "scratch"                 # per-run working space
    CACHE = "cache"                     # vendor/file-handle cache, TTL/GC
    SECRETS = "secrets"                 # credentials/keys
    CONFIG_RO = "config_ro"             # read-only configuration
    IPC_BRIDGE = "ipc_bridge"           # local agent↔agent channel (socket/pipe)


class Layer(str, Enum):
    """Store layer (diagram 1)."""

    CANONICAL = "canonical"       # L1 — durable object store, BYOS, residency-governed
    DERIVED = "derived"           # L2 — disposable, rebuildable from canonical
    VENDOR_CACHE = "vendor_cache" # L3 — TTL/GC vendor materialization
    EPHEMERAL = "ephemeral"       # L6 — tool-runtime scratch, gone at exit
    CONFIG = "config"             # read-only config plane
    NODE_LOCAL = "node_local"     # IPC — never leaves the node


class Retention(str, Enum):
    DURABLE = "durable"       # kept; deletion is policy-gated (retention scheduler + legal hold)
    REBUILDABLE = "rebuildable"  # may be GC'd freely; rebuilt from canonical
    TTL = "ttl"              # vendor cache: expires on TTL/GC, re-materialized from canonical
    EPHEMERAL = "ephemeral"  # never persisted beyond the run
    MANAGED_RO = "managed_ro"  # lifecycle owned by its source (ConfigMap/Secret)


class Runtime(str, Enum):
    KUBERNETES = "kubernetes"
    DOCKER = "docker"
    PODMAN = "podman"  # rootful on this Mac


class Direction(str, Enum):
    """Data-flow direction relative to the WORKLOAD — orthogonal to lifecycle/sensitivity.

    A workload's security model is directional: read-only inputs come IN, exactly one durable
    channel goes OUT (the only mount whose contents survive the pod and the one place egress
    attestation lives), everything else is node-local. Encoding direction lets us enforce the
    single-egress-chokepoint invariant by construction instead of hoping the manifest is right.
    """

    INGRESS = "ingress"              # read-only input the workload consumes
    EGRESS = "egress"                # the durable write channel — survives the pod, attested
    BIDIRECTIONAL = "bidirectional"  # both (discouraged: two attestation points)
    NONE = "none"                    # node-local; never crosses the workload boundary durably


class LinkAvailability(str, Enum):
    """Whether the edge↔twin link is dependable. This — with durability — decides copy vs
    reference semantics, and therefore whether the conflict-resolution machinery is even needed.
    """

    RELIABLE = "reliable"          # reference-mount the store: one object, no divergence
    INTERMITTENT = "intermittent"  # must copy + snapshot + reconcile (CRF/ternary earns its keep)


@dataclass(frozen=True)
class IntentBinding:
    """The full, policy-bearing binding for one intent."""

    intent: MountIntent
    layer: Layer
    retention: Retention
    direction: Direction  # workload-boundary flow — the single-egress-chokepoint axis
    may_egress: bool   # may this data ever leave the DEVICE (e.g. sync to the cloud twin)?
    may_cache: bool    # may this be vendor-materialized (Layer 3 file handle)?
    read_only: bool
    # verified_immutable: immutability is STRUCTURAL (squashfs/erofs, no write path in the kernel
    # driver) and, in the sovereign form, CRYPTOGRAPHIC (dm-verity root hash pinned in the
    # manifest) — categorically stronger than read_only, which is only a mount flag another view
    # can bypass. Corpus that must be provably unmutated crawl-time→query-time requires this.
    verified_immutable: bool = False
    # tenancy_in_source: the tenant/session is bound in the mount SOURCE string (e.g.
    # `store:<tenant>:/path`), unforgeable from inside the guest — construction-enforced isolation,
    # not a path prefix or an admission rule a bad manifest can get wrong.
    tenancy_in_source: bool = False
    # backend per runtime: (kind, options)
    kubernetes: tuple[str, str] = ("", "")
    docker: tuple[str, str] = ("", "")
    podman: tuple[str, str] = ("", "")

    def backend(self, runtime: Runtime) -> tuple[str, str]:
        return {
            Runtime.KUBERNETES: self.kubernetes,
            Runtime.DOCKER: self.docker,
            Runtime.PODMAN: self.podman,
        }[runtime]


# The single source of truth. Egress is ALLOWED only for canonical + curated (and even then the
# Policy Engine still governs it); everything else is rebuildable, ephemeral, or sensitive and
# MUST NOT leave the device. This is enforcement-by-construction, not documentation.
_BINDINGS: dict[MountIntent, IntentBinding] = {
    # canonical_data is the ONE durable write channel: direction=egress, tenant bound in the
    # mount source (construction-enforced isolation). Link-aware backend (reference vs copy) is
    # chosen by select_backend(); the static backend is the durable store fallback.
    MountIntent.CANONICAL_DATA: IntentBinding(
        MountIntent.CANONICAL_DATA, Layer.CANONICAL, Retention.DURABLE,
        direction=Direction.EGRESS, may_egress=True, may_cache=True, read_only=False,
        tenancy_in_source=True,
        kubernetes=("persistentVolumeClaim", "topolvm/local/nfs"),
        docker=("volume", "local/driver"),
        podman=("volume", "local"),
    ),
    # curated_corpus is a read-only INGRESS input, and its default is a verified-immutable image
    # (squashfs/erofs + dm-verity, root hash pinned in the manifest) — provably unmutated
    # crawl-time→query-time, which `readOnly: true` cannot guarantee. This wires the `type=image`
    # backend to curated_corpus as T0.
    MountIntent.CURATED_CORPUS: IntentBinding(
        MountIntent.CURATED_CORPUS, Layer.CANONICAL, Retention.DURABLE,
        direction=Direction.INGRESS, may_egress=True, may_cache=True, read_only=True,
        verified_immutable=True,
        kubernetes=("image", "verity-ro"),
        docker=("image", "verity-ro"),
        podman=("image", "squashfs+dm-verity,ro"),
    ),
    MountIntent.DERIVED_INDEX: IntentBinding(
        MountIntent.DERIVED_INDEX, Layer.DERIVED, Retention.REBUILDABLE,
        direction=Direction.NONE, may_egress=False, may_cache=False, read_only=False,
        kubernetes=("persistentVolumeClaim", "topolvm/local"),
        docker=("volume", "local"),
        podman=("volume", "local"),
    ),
    MountIntent.SCRATCH: IntentBinding(
        MountIntent.SCRATCH, Layer.EPHEMERAL, Retention.EPHEMERAL,
        direction=Direction.NONE, may_egress=False, may_cache=False, read_only=False,
        kubernetes=("emptyDir", ""),
        docker=("tmpfs", ""),
        podman=("tmpfs", ""),
    ),
    MountIntent.CACHE: IntentBinding(
        MountIntent.CACHE, Layer.VENDOR_CACHE, Retention.TTL,
        direction=Direction.NONE, may_egress=False, may_cache=True, read_only=False,
        kubernetes=("emptyDir", ""),
        docker=("tmpfs", ""),
        podman=("overlay", ":O"),
    ),
    MountIntent.SECRETS: IntentBinding(
        MountIntent.SECRETS, Layer.EPHEMERAL, Retention.EPHEMERAL,
        direction=Direction.INGRESS, may_egress=False, may_cache=False, read_only=True,
        kubernetes=("secret", "tmpfs-copy"),
        docker=("tmpfs", "secret"),
        podman=("secret", "mount/env"),
    ),
    MountIntent.CONFIG_RO: IntentBinding(
        MountIntent.CONFIG_RO, Layer.CONFIG, Retention.MANAGED_RO,
        direction=Direction.INGRESS, may_egress=False, may_cache=False, read_only=True,
        kubernetes=("configMap", "projected"),
        docker=("bind", "ro"),
        podman=("bind", "ro"),
    ),
    MountIntent.IPC_BRIDGE: IntentBinding(
        MountIntent.IPC_BRIDGE, Layer.NODE_LOCAL, Retention.EPHEMERAL,
        direction=Direction.NONE, may_egress=False, may_cache=False, read_only=False,
        kubernetes=("emptyDir", "socket"),
        docker=("npipe", "named-pipe"),
        podman=("bind", "socket"),
    ),
}


def binding(intent: MountIntent) -> IntentBinding:
    return _BINDINGS[intent]


def resolve(intent: MountIntent, runtime: Runtime,
            link: LinkAvailability = LinkAvailability.RELIABLE) -> dict:
    """The backend mount spec + policy for an intent — the SECURE form by default.

    The real signature is `intent × link_availability × durability → backend`: a durable
    egress channel over a RELIABLE link is reference-mounted (one object, no copy, no
    divergence, no conflict-resolution); over an INTERMITTENT link it is forced into
    copy+snapshot+reconcile, which is the only case that needs the CRF/ternary machinery.
    """
    b = binding(intent)
    kind, options = b.backend(runtime)
    sync = _sync_semantics(b, link)
    out = {
        "intent": intent.value,
        "runtime": runtime.value,
        "layer": b.layer.value,
        "retention": b.retention.value,
        "direction": b.direction.value,
        "backend": {"kind": kind, "options": options},
        "read_only": b.read_only,
        "verified_immutable": b.verified_immutable,
        "tenancy_in_source": b.tenancy_in_source,
        "sync_semantics": sync["semantics"],
        "requires_conflict_resolution": sync["requires_conflict_resolution"],
        "policy": {"may_egress": b.may_egress, "may_cache": b.may_cache},
    }
    if b.verified_immutable:
        # a verified-immutable mount is meaningless without its pinned root hash; the manifest
        # MUST supply it (validators enforce presence). Signal the requirement here.
        out["requires_verity_root_hash"] = True
    return out


def _sync_semantics(b: IntentBinding, link: LinkAvailability) -> dict:
    """Copy vs reference, and whether conflict-resolution is needed — a function of the
    (durability × link) product, not a property of the data."""
    durable_boundary = b.direction in (Direction.EGRESS, Direction.BIDIRECTIONAL)
    if not durable_boundary:
        return {"semantics": "node_local", "requires_conflict_resolution": False}
    if link is LinkAvailability.RELIABLE:
        # reference-mount the store: no second copy, so no divergence, so no reconciliation.
        return {"semantics": "reference", "requires_conflict_resolution": False}
    # intermittent: copy + snapshot + reconcile — this is where SP-EVAL-CRF-001 earns its keep.
    return {"semantics": "copy", "requires_conflict_resolution": True}


def direction(intent: MountIntent) -> Direction:
    return binding(intent).direction


def verified_immutable(intent: MountIntent) -> bool:
    return binding(intent).verified_immutable


def tenant_scoped_source(store: str, tenant: str, path: str) -> str:
    """Construct a tenant-bound mount source, e.g. `store:<tenant>:/path`.

    Isolation is bound at mount time in the source string and is unforgeable from inside the
    guest — construction-enforced, not a path prefix or an admission rule a bad manifest can
    get wrong. Use for every canonical (egress) mount.
    """
    tenant = tenant.strip().strip(":")
    if not tenant:
        raise ValueError("tenant must be non-empty (tenancy is construction-enforced)")
    return f"{store}:{tenant}:{path if path.startswith('/') else '/' + path}"


# ── Policy gates (Layer 5: the Policy Engine gates egress / caching / deletion) ──────────────
def may_egress(intent: MountIntent) -> bool:
    """May data with this intent ever leave the device (e.g. sync to the cloud twin)?"""
    return binding(intent).may_egress


def may_cache(intent: MountIntent) -> bool:
    """May this be vendor-materialized into a Layer-3 file handle?"""
    return binding(intent).may_cache


def may_delete(intent: MountIntent) -> bool:
    """May this be GC'd/deleted without a retention decision? Durable data is retention-gated;
    rebuildable/ttl/ephemeral data is freely collectable."""
    return binding(intent).retention != Retention.DURABLE


EGRESSABLE_INTENTS: frozenset[MountIntent] = frozenset(i for i in MountIntent if may_egress(i))

# Intents whose workload-boundary DIRECTION is egress — the durable-write chokepoint(s).
EGRESS_DIRECTION_INTENTS: frozenset[MountIntent] = frozenset(
    i for i in MountIntent if binding(i).direction in (Direction.EGRESS, Direction.BIDIRECTIONAL)
)


def check_single_egress(intents) -> list[str]:
    """Enforce the single-egress-chokepoint invariant on a workload's set of mount intents.

    At most one egress mount per workload — the only mount whose contents survive the pod, so
    egress attestation and chain-of-custody have exactly one place to live. Returns a list of
    violation strings (empty == ok). This is the workload-level counterpart to the per-device
    may_egress policy.
    """
    egress = [i for i in intents if i in EGRESS_DIRECTION_INTENTS]
    if len(egress) > 1:
        names = ", ".join(sorted(i.value for i in egress))
        return [f"workload declares {len(egress)} egress mounts ({names}); at most one is allowed "
                f"— egress must have a single durable-write chokepoint"]
    return []
