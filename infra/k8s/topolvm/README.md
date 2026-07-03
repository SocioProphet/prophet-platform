# TopoLVM — edge local-flash storage

Provides a `topolvm-provisioner` StorageClass so stateful edge workloads (the
per-person **HellGraph** RocksDB store first among them) get PersistentVolumes
carved from **local NVMe/flash** on the k3s node, rather than a network or cloud
disk. This is what makes the "local instance + flash disk" tier real: the graph
lives on-device, and only non-private projections sync to the cloud twin.

## What's here

- `base/storageclass.yaml` — the `topolvm-provisioner` StorageClass
  (`WaitForFirstConsumer`, `allowVolumeExpansion`, device-class `ssd`).

## Prerequisite: the TopoLVM operator (not in this kustomize base)

The StorageClass is inert until the TopoLVM controller + `lvmd` DaemonSet are
installed on the edge cluster and a volume group exists on the flash device.
On each edge node:

```bash
# 1. A volume group on the flash disk (example device /dev/nvme0n1):
sudo vgcreate ssd-vg /dev/nvme0n1

# 2. lvmd device-class config maps "ssd" → that VG (DaemonSet config):
#    device-classes:
#      - name: ssd
#        volume-group: ssd-vg
#        default: true
```

Then install the operator (Helm):

```bash
helm repo add topolvm https://topolvm.github.io/topolvm
helm install topolvm topolvm/topolvm -n topolvm-system --create-namespace \
  --set lvmd.deviceClasses[0].name=ssd \
  --set lvmd.deviceClasses[0].volume-group=ssd-vg \
  --set lvmd.deviceClasses[0].default=true
```

## Usage

Only **edge** overlays reference this class — e.g.
`infra/k8s/hellgraph/overlays/edge` patches the HellGraph
`volumeClaimTemplates` `storageClassName` to `topolvm-provisioner`. The `base`
and `p0-lab` paths leave `storageClassName` unset (cluster default), so nothing
here changes cloud/lab deployments.
