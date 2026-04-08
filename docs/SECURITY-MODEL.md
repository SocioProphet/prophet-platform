# Security Model — Prophet Platform

## Principles

1. **Defense in depth** — multiple layers; no single trust boundary.
2. **Least privilege** — workloads run as non-root, drop all unnecessary capabilities.
3. **Confidentiality by default** — AEAD framing on all intra-service communication in production.
4. **Audit trail** — every request carries a correlation / audit ID; logs are structured and immutable.

---

## Trust boundaries

```
Internet
  │  (HTTPS / mTLS)
  ▼
Gateway (apps/gateway)   ← only public-facing component
  │  (TritRPC over UDS)
  ▼
API service (apps/api)   ← never directly accessible from outside
  │  (internal calls)
  ▼
Storage / downstream services
```

- The **gateway** terminates TLS at the edge. It must enforce strict route allow-listing.
- The **API service** listens only on a Unix Domain Socket; it must never bind a public TCP port.
- **Inter-node** communication (if any) should use mTLS with mutual certificate verification.

---

## AEAD encryption (TritRPC framing)

See [TRITRPC_SPEC.md](TRITRPC_SPEC.md) for the full frame layout.

- Cipher: ChaCha20-Poly1305 or AES-256-GCM (config-selected).
- Key: `TRITRPC_AEAD_KEY` — 32-byte hex, loaded from a secret store.
- Nonce: 96-bit per-connection counter; nonce reuse is fatal and must be detected.
- Replay guard: monotonic counter + LRU window.

The exemplar API currently runs **plaintext** for legibility. Swap in the library before production.

---

## Kubernetes hardening

- Run containers as non-root (`runAsNonRoot: true`, `runAsUser: 1000`).
- Drop all capabilities (`capabilities.drop: [ALL]`).
- Apply `seccompProfile: RuntimeDefault` (or stricter).
- Use `ClusterIP` services; avoid `NodePort` / `LoadBalancer` for internal services.
- Use namespaces to isolate workloads.
- Restrict Argo CD repo allow-lists; enforce Cosign/Sigstore manifest and image signatures.

---

## Secrets

- `TRITRPC_AEAD_KEY` must never be committed to git.
- Use sealed secrets or an external secret operator in production.
- Rotate regularly; see [RUNBOOK.md](RUNBOOK.md#rotating-secrets).

---

## Threat model (summary)

| Threat | Mitigation |
|--------|-----------|
| Network eavesdropping | AEAD framing; TLS at edge |
| Replay attacks | Nonce monotonic counter + LRU window |
| Container escape | Non-root + capability drop + seccomp |
| Supply chain | Dependency pinning; image digest pinning (planned) |
| Secrets exposure | No secrets in git; Kubernetes Secret + rotation |
| Lateral movement | UDS-only API; namespace isolation |
