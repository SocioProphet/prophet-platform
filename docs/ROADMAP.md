# Roadmap (Initial 11 Steps)

1) Ship a minimal TritRPC library and drop it into `apps/api` (replace plaintext).
2) Add AEAD key management (env→K8s Secret→sealed-secret).
3) Define formal IDL for TritRPC (proto-like schema) and codegen stubs.
4) Implement server-streaming for LLM output.
5) Add structured logging with redaction + audit IDs.
6) Harden gateway with mTLS at the edge and strict route allow-list.
7) Introduce multi-tenant authn/z (OIDC provider; edge only).
8) Add e2e tests that spawn UDS server + gateway and probe basic RPCs.
9) Wire Argo CD app-of-apps to dev/prod overlays.
10) Add perf budget checks (latency/CPU/mem) to CI.
11) Stand up canary deployments (progressive delivery) via Argo Rollouts.
