# mount-intent

Declare storage by **intent**, not by mechanism — and get the backend mount **and** the
retention/egress/caching **policy** by construction. This is the storage-side counterpart to the
ER plane's egress-masking / fog-scope discipline: sensitive or rebuildable data never leaves the
device unless an intent explicitly, policy-permitted allows it.

## Why

The layered store model (canonical L1 → derived/rebuildable L2 → vendor-cache/TTL L3 → tool-runtime
ephemeral L6) and its Policy Engine (gates **egress / caching / deletion**, records to an
append-only audit log) implied a policy that used to live only in reviewers' heads and hand-wired
volume manifests. This library makes it code.

## Intent → layer → policy

| intent | layer | retention | may egress | may vendor-cache |
|--------|-------|-----------|:----------:|:----------------:|
| `canonical_data` | canonical (L1) | durable | ✅ | ✅ |
| `curated_corpus` | canonical (L1) | durable | ✅ | ✅ |
| `derived_index` | derived (L2) | rebuildable | ❌ (rebuild at the twin) | ❌ |
| `cache` | vendor-cache (L3) | ttl | ❌ | ✅ |
| `scratch` | ephemeral (L6) | ephemeral | ❌ | ❌ |
| `secrets` | ephemeral | ephemeral | ❌ **never** | ❌ |
| `config_ro` | config | managed-ro | ❌ | ❌ |
| `ipc_bridge` | node-local | ephemeral | ❌ | ❌ |

**Only `canonical_data` and `curated_corpus` may ever egress** (and even then residency/ACLs still
apply). Everything else is rebuildable, ephemeral, or sensitive and stays on the device.

## Use

```python
from mount_intent import MountIntent, Runtime, resolve, may_egress, PolicyDecision

resolve(MountIntent.DERIVED_INDEX, Runtime.PODMAN)
# {'backend': {'kind': 'volume', 'options': 'local'}, 'retention': 'rebuildable',
#  'policy': {'may_egress': False, 'may_cache': False}, ...}

may_egress(MountIntent.SECRETS)            # False — never leaves the device
PolicyDecision.egress(MountIntent.SECRETS) # auditable decision (gate, allowed, reason, decided_at)
```

`resolve` maps to the right backend per runtime — K8s PV/PVC (TopoLVM/local/NFS), emptyDir,
Secret, configMap; Docker volume/tmpfs/bind/npipe; Podman volume/tmpfs/`:O` overlay/secret/bind.

## Lifecycle

`mount_intent.lifecycle` encodes the artifact state machine
(`IngestedRaw → Normalized → Extracted → Indexed → Served → {VendorMaterialized, FlaggedRetention,
LegalHold} → Deleted`). `transition()` refuses illegal moves and **blocks deletion under a legal
hold**.

## Enforcement

`tools/validate_mount_intent_egress.py` gates the build: any edge→cloud-twin sync Job/CronJob must
declare `mount-intent.socioprophet.io/egress: <intent>[,...]`, and every declared intent must be
egress-allowed. Adding `derived_index` or `secrets` to a sync job — or omitting the annotation —
fails CI. Runs in `mount-intent.yml`.
