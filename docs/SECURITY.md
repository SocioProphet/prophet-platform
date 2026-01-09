# Security Notes

- Prefer **UDS** for intra-host communication; disable TCP unless strictly necessary.
- Load **TRITRPC_AEAD_KEY** (32 bytes hex) from a secret store for production.
- Pin container users to non-root, drop capabilities, and apply seccomp/apparmor.
- Prefer **ClusterIP** + sidecars over public NodePorts; isolate namespaces.
- Argo CD: restrict repo allow-lists and enforce signature verification (Cosign/Sigstore) for manifests and images.
