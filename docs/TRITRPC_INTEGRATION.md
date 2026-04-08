# TriTRPC integration note

This repository integrates TritRPC at the platform boundary.

## Intended use here

- use Unix Domain Sockets as the default intra-host trust boundary
- let the gateway terminate browser-facing HTTP(S)/WebSocket traffic and relay inward over the owning runtime boundary
- keep protocol framing and canonical transport details in `TriTRPC`

## What should not happen here

This repository should not become a second protocol specification home.

If a reader needs canonical framing details, fixture semantics, or compliance-oriented transport notes, direct them to `TriTRPC`.

## Platform responsibility

The platform repo is responsible for:

- showing where TritRPC fits in deployment topology
- documenting how apps, gateways, and infrastructure consume the protocol
- documenting operational boundary choices such as UDS-first deployment

It is not responsible for redefining the protocol itself.
