# Matrix/QES identity alignment

This note aligns the Matrix/QES operator lane with the platform identity contract lane under `contracts/identity`.

## Why this exists

Matrix/QES operator actions are security-relevant platform events. They can acknowledge incidents, request replay, suppress threads, resolve cases, and eventually trigger orchestrated workflows.

That means Matrix-native identifiers such as room IDs, thread IDs, and Matrix user IDs are not enough by themselves. They must be bound to platform identity context before they become durable operator authority.

## Current identity contract inputs

The current platform identity lane includes:

- `contracts/identity/IdentitySubjectContext.v0.1.json`
- `contracts/identity/IdentitySessionContext.v0.1.json`
- `contracts/identity/IdentityProofIngressRecord.v0.1.json`

Matrix/QES should consume those shapes instead of defining a parallel identity universe.

## Matrix/QES actor mapping

The Matrix/QES event field `actor_id` is the platform actor reference.

For Matrix-originated operator commands, the mapping should be:

| Matrix value | Platform value | Notes |
|---|---|---|
| Matrix user ID | `actor_id` or upstream subject | Example: `@operator:matrix.example` |
| Matrix room ID | `room_id` | Room-level operator context |
| Matrix event ID | `message_event_id` | Command provenance and replay evidence |
| Matrix thread/root event | `thread_id` | Incident thread or operator workflow binding |
| Identity subject | `subject_id` | From `IdentitySubjectContext` after resolution |
| Identity session | `session_id` | From `IdentitySessionContext` when available |

The durable operator event should preserve both the Matrix-native values and the platform identity resolution result.

## Required resolution behavior

Before a Matrix/QES command becomes authority-bearing, the runtime should resolve:

1. Matrix user ID to a platform subject.
2. Platform subject to current session context when session context is available.
3. Subject/session context to an assurance level.
4. Assurance level to allowed command families.
5. Command family to policy decision and evidence refs.

## Event consequences

`matrix.operator.action.v1` should remain the durable action event. Future revisions should add optional identity bindings without breaking the current contract:

- `subject_id`
- `session_id`
- `assurance_level`
- `identity_evidence_refs`
- `policy_refs`

For now, the first slice keeps the minimal actor field while documenting the intended binding.

## Control-plane consequences

`control.resolution.snapshot.v1` should use the identity-resolved `targeting_key` where possible. If only a Matrix user ID is available, the snapshot should mark the source as Matrix-native and classify the resolution as provisional.

## Replay consequences

`replay.requested.v1` should treat `requested_by` as a platform actor reference, not merely a display name. If the replay request originated from Matrix, room and thread IDs preserve the Matrix provenance separately.

## Non-goals

This note does not implement authentication, Matrix SSO, passkey proofing, OIDC/SAML federation, or workload identity issuance.

Those belong in the identity-prime or ingress-auth lane. Matrix/QES only consumes the resolved identity context.

## Next implementation step

The next implementation slice should add an identity resolver seam to `apps/matrix-qes-operator` that can accept a Matrix user ID and return a resolved `IdentitySubjectContext` reference plus assurance metadata.
