# TriTRPC Source of Truth

`prophet-platform` does **not** maintain an independent TriTRPC wire spec.

The normative transport source of truth is the upstream `SocioProphet/TriTRPC` repository, where **v1** is explicitly described as the stable interoperability surface and **vNext** remains experimental. The stable repo guarantees canonical encoding, deterministic fixtures, strict verification, and Go/Rust parity. The Go/Rust ports use **XChaCha20-Poly1305** with **24-byte nonces** for authenticated frames, and the readiness checklist says fixtures and repacking must reproduce identical bytes. The full spec copy in that repo also says the Go/Rust ports currently rely on explicit per-frame nonces rather than a rolling nonce scheme.

This repository only defines the **platform binding** needed to carry stable TriTRPC v1 envelopes over UDS/TCP streams. See `docs/TRITRPC_PLATFORM_BINDING.md`.
