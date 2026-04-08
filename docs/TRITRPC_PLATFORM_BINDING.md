# Platform TriTRPC Binding

This file defines the **platform-specific stream binding** for stable TriTRPC v1 envelopes.

## Record layout

Each stream record is:

```text
| frame_len_be_u32 | nonce_24 | tritrpc_v1_envelope_bytes |
```

- `frame_len_be_u32` is the length of the TriTRPC envelope bytes only.
- `nonce_24` is the 24-byte XChaCha20-Poly1305 nonce carried out-of-band.
- `tritrpc_v1_envelope_bytes` is the upstream canonical envelope, including the AEAD tag field.

## AEAD verification

- Use the upstream TriTRPC v1 envelope decoder.
- Reconstruct `AAD = envelope bytes up to (but not including) the final tag field length prefix`, matching the upstream Go/Rust readiness notes.
- Verify the tag with XChaCha20-Poly1305 and the 24-byte out-of-band nonce.

## Minimal health route in this phase

Service: `platform.health.v1`

Methods:
- `Health.Ping.REQ`
- `Health.Ping.RES`

Payloads are JSON bytes carried inside the envelope payload lane for bootstrap simplicity.

## Endpoint forms

- `unix:///tmp/socioprophet.sock`
- `tcp://0.0.0.0:9000`
- `tcp://socioprophet-api:9000`

Bare `/path.sock` values are treated as Unix sockets. Bare `host:port` values are treated as TCP.
