# Platform service classes

`prophet-platform` contains more than one kind of runtime. Treating them as one class causes deployment errors and security confusion.

## Classes

### Edge services
Browser-facing ingress or translation services.
Examples: `apps/gateway`

### Cluster services
Internal networked runtimes deployed through K8s, service mesh, or equivalent.
Examples: `apps/api`, future `apps/agentplane`

### Local daemons
Per-device or per-user services managed through distro packaging and local supervisors.
Examples: `apps/lampstand`

### Standards inputs
Pinned upstream standards and contract packs used to generate or validate platform artifacts.
Examples: `TriTRPC`, `ontogenesis`, `semantic-serdes`, `socioprophet-standards-storage`

## Why this matters
Local daemons still belong in the platform repo, but they should not be forced into Argo/K8s manifests just to "look uniform."
