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

## Directional defaults (isolation by construction)

Intent encodes *lifecycle* and *sensitivity*; it now also encodes **direction** and resolves
to the **secure form by default**. Four invariants stick from day one:

- **Direction axis** — every intent is `ingress` (ro input), `egress` (the one durable write
  channel that survives the pod), or `none` (node-local). `canonical_data` is the *only* egress
  intent. **At most one egress mount per workload** (`WorkloadDeclaration` /
  `check_single_egress` / `validate_mount_intent_workload.py`) — one chokepoint, one place for
  egress attestation.
- **Verified-immutable corpus** — `curated_corpus` defaults to a `type=image` backend
  (squashfs/erofs + **dm-verity**), and a `MountDeclaration` for it **must pin a
  `verity_root_hash`**. Corpus integrity becomes a signature check, not a `readOnly: true`
  trust assertion another view can bypass.
- **Construction-enforced tenancy** — `canonical_data` binds the tenant in the mount *source*
  (`tenant_scoped_source(store, tenant, path)` → `store:<tenant>:/path`), unforgeable from
  inside the guest — not a path prefix or an admission rule a bad manifest can get wrong.
- **`intent × link_availability × durability → backend`** — an egress mount over a *reliable*
  link is **reference-mounted** (one object, no copy, no divergence, no reconciliation); over an
  *intermittent* link it is forced into copy+snapshot+reconcile — the only case that needs the
  conflict-resolution machinery. `resolve(intent, runtime, link)` returns `sync_semantics` and
  `requires_conflict_resolution` accordingly.

Workload manifests declare intents with
`mount-intent.socioprophet.io/mounts: <vol>=<intent>,...` and pin verity with
`mount-intent.socioprophet.io/verity.<vol>: <64-hex>`; both CI validators fail the build on a
violation.
