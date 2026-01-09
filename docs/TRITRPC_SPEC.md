# TritRPC Framing (Working Spec Excerpt)

> Goal: small, auditable message framing for RPC over UDS/TCP with replay guard.

**Frame (logical):**
```
| prelude (2B type, 4B len) | nonce (12B) | ciphertext (len) | tag (16B) |
```
- AEAD: ChaCha20-Poly1305 or AES-256-GCM (select via config)
- Nonce: 96-bit with per-connection counter (reject reuse)
- AAD: `{channel_id||crc16(payload_type||len)||ts32}` (example)
- Replay guard: monotonic counter + LRU window
- CRC16: optional lightweight redundancy for pre-decrypt sanity

**Message types (examples):**
- `0x0001` Health.Ping
- `0x0100` LLM.ChatStream (server-stream)
- `0x0200` RAG.Query

This repo’s API example runs plaintext `PING/PONG` to keep the example tiny. Swap in your TritRPC library as it matures.
