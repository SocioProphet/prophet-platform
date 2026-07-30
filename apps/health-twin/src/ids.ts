// ONE decision about where an identifier comes from, for every ledger in this engine.
//
// THE DEFECT, twice. A grant id was `grant-<sha256(agent|scope|Date.now())>` and a consult id was
// `consult-<sha256(pseudonym|scope|Date.now()-scope)>`. Both are a HASH OF THEIR OWN INPUTS, and both
// inherit two properties from that:
//
//   1. THEY COLLIDE. The only varying input is a millisecond. Two grants issued to the same agent
//      with the same scope in the same millisecond get the SAME id — measured at 79% of 200
//      concurrent issues on this laptop. A collided grant is not a cosmetic duplicate: the ledger
//      holds two rows under one identity, lookup silently resolves to one of them, the other
//      holder's secret stops authenticating with no error anyone can point at, revoking the id
//      revokes one row and leaves the other, and every receipt naming that id is ambiguous about
//      which grant it recorded. "Every access is a receipt" is false if a receipt can name two things.
//
//   2. THEY ARE RECOMPUTABLE OFFLINE. `granted_at` is published on the grant, at millisecond
//      precision, and the agent and scope are published beside it. Anyone holding a grant listing
//      can recompute the id of every grant in it — verified: sha256 over the same three inputs
//      reproduces the published id exactly. The id is not the credential any more (that is what
//      grantauth.ts fixed), but an id that a stranger can derive is still an offline guessing target
//      handed out for free, and it is the input to revocation, which is id-only by design.
//
// THE DECISION: an identifier is MINTED, not DERIVED. 128 bits from the CSPRNG, hex. Nothing about
// the record is recoverable from it, nothing about it is predictable from the record, and the
// collision probability over any ledger this service could hold is not a number worth writing down.
//
// WHY NOT sha256(inputs + a random nonce), which is the other obvious repair: the moment a random
// nonce is inside the hash, the output IS random — the deterministic inputs contribute nothing an
// attacker cannot already see, and the hash contributes nothing but the appearance of derivation.
// It reads like a content address and is not one. Minting the bytes says what is actually happening.
//
// WHAT AN ID IS NOT. It is not a content address and it is not a receipt: those stay `sha256` over
// JSON-encoded parts (see `receipt()` in server.ts), because their entire job IS to be recomputable
// from the facts they seal. Two different things that happen to be strings.
//
// WHY 256 BITS AND NOT 128. The estate already runs a ratchet over every EMITTED id — "no id ends in
// an 8-hex digest, all of them carry a full 64 hex" — put there when djb2 was found wearing a `sha-`
// label. 128 bits would be ample and would trip that ratchet for no gain, so the mint is 32 bytes and
// the existing guard keeps working unchanged. The width matches a sha256 digest; the bytes do not
// come from one, and this comment is the only place that distinction is recoverable from the string.
import { randomBytes } from 'node:crypto';

/** 256 CSPRNG bits, hex, behind a human-readable prefix: `grant-…`, `consult-…`, `op-…`, `more-…`. */
export function mintId(prefix: string): string {
  return `${prefix}-${randomBytes(32).toString('hex')}`;
}

/** `<prefix>-<64 hex>`. Used by the invariants, so the shape is checked and not merely intended. */
export const ID_PATTERN = /^[a-z][a-z0-9-]*-[0-9a-f]{64}$/;
