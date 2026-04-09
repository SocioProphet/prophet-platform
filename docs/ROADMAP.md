# Roadmap (Current 11 Steps)

1) Converge `eval-fabric-api` on one canonical default runtime and keep seeded/persisted alternates non-default.
2) Replace placeholder pins in `standards.lock.yaml` with real commits and generated artifact diffs.
3) Add AEAD key management (env -> K8s Secret -> sealed-secret / equivalent).
4) Define formal IDL for TriTRPC and codegen stubs.
5) Add structured logging with redaction + audit/correlation IDs.
6) Wire eval-fabric outputs onto the platform `EventEnvelope` / `EvidenceReceipt` spine.
7) Expose Lampstand discovery/receipt catalog through a platform service boundary.
8) Introduce runtime receipt verification and policy flow for `knowledge-reason`.
9) Wire Argo CD app-of-apps to dev/prod overlays, including additional services once they are canonicalized.
10) Add perf budget checks (latency/CPU/memory) to CI.
11) Stand up canary deployments / progressive delivery for cluster services.
