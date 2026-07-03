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


@dataclass(frozen=True)
class IntentBinding:
    """The full, policy-bearing binding for one intent."""

    intent: MountIntent
    layer: Layer
    retention: Retention
    may_egress: bool   # may this data ever leave the device (e.g. sync to the cloud twin)?
    may_cache: bool    # may this be vendor-materialized (Layer 3 file handle)?
    read_only: bool
    # backend per runtime: (kind, options)
    kubernetes: tuple[str, str]
    docker: tuple[str, str]
    podman: tuple[str, str]

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
    MountIntent.CANONICAL_DATA: IntentBinding(
        MountIntent.CANONICAL_DATA, Layer.CANONICAL, Retention.DURABLE,
        may_egress=True, may_cache=True, read_only=False,
        kubernetes=("persistentVolumeClaim", "topolvm/local/nfs"),
        docker=("volume", "local/driver"),
        podman=("volume", "local"),
    ),
    MountIntent.CURATED_CORPUS: IntentBinding(
        MountIntent.CURATED_CORPUS, Layer.CANONICAL, Retention.DURABLE,
        may_egress=True, may_cache=True, read_only=True,
        kubernetes=("persistentVolumeClaim", "topolvm/local/nfs"),
        docker=("volume", "local/driver"),
        podman=("volume", "local"),
    ),
    MountIntent.DERIVED_INDEX: IntentBinding(
        MountIntent.DERIVED_INDEX, Layer.DERIVED, Retention.REBUILDABLE,
        may_egress=False, may_cache=False, read_only=False,
        kubernetes=("persistentVolumeClaim", "topolvm/local"),
        docker=("volume", "local"),
        podman=("volume", "local"),
    ),
    MountIntent.SCRATCH: IntentBinding(
        MountIntent.SCRATCH, Layer.EPHEMERAL, Retention.EPHEMERAL,
        may_egress=False, may_cache=False, read_only=False,
        kubernetes=("emptyDir", ""),
        docker=("tmpfs", ""),
        podman=("tmpfs", ""),
    ),
    MountIntent.CACHE: IntentBinding(
        MountIntent.CACHE, Layer.VENDOR_CACHE, Retention.TTL,
        may_egress=False, may_cache=True, read_only=False,
        kubernetes=("emptyDir", ""),
        docker=("tmpfs", ""),
        podman=("overlay", ":O"),
    ),
    MountIntent.SECRETS: IntentBinding(
        MountIntent.SECRETS, Layer.EPHEMERAL, Retention.EPHEMERAL,
        may_egress=False, may_cache=False, read_only=True,
        kubernetes=("secret", "tmpfs-copy"),
        docker=("tmpfs", "secret"),
        podman=("secret", "mount/env"),
    ),
    MountIntent.CONFIG_RO: IntentBinding(
        MountIntent.CONFIG_RO, Layer.CONFIG, Retention.MANAGED_RO,
        may_egress=False, may_cache=False, read_only=True,
        kubernetes=("configMap", "projected"),
        docker=("bind", "ro"),
        podman=("bind", "ro"),
    ),
    MountIntent.IPC_BRIDGE: IntentBinding(
        MountIntent.IPC_BRIDGE, Layer.NODE_LOCAL, Retention.EPHEMERAL,
        may_egress=False, may_cache=False, read_only=False,
        kubernetes=("emptyDir", "socket"),
        docker=("npipe", "named-pipe"),
        podman=("bind", "socket"),
    ),
}


def binding(intent: MountIntent) -> IntentBinding:
    return _BINDINGS[intent]


def resolve(intent: MountIntent, runtime: Runtime) -> dict:
    """The backend mount spec + policy for an intent on a given runtime."""
    b = binding(intent)
    kind, options = b.backend(runtime)
    return {
        "intent": intent.value,
        "runtime": runtime.value,
        "layer": b.layer.value,
        "retention": b.retention.value,
        "backend": {"kind": kind, "options": options},
        "read_only": b.read_only,
        "policy": {"may_egress": b.may_egress, "may_cache": b.may_cache},
    }


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
