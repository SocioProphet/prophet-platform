# WordOps Moderation and Publication Profile v0.1

## Decision

### P0 production baseline
Use **Mjolnir** as the primary active moderation bot for the public Matrix edge.

Rationale:
- broad production-proven moderation surface
- policy-list driven bans and protections
- room/server ACL operations
- abuse-response posture that is practical today

### P1 / staging lane
Evaluate **policyserv** in staging as the proactive moderation path.

Rationale:
- policy-server style moderation is the long-term direction for pre-accept event screening
- current Matrix direction makes it strategically important
- operational maturity should be proven in staging before it becomes the primary enforcement actor

### Optional pilot
Evaluate **Draupnir** as a management-room/operator UX layer where its workflow is useful, but do not make it the P0 mandatory enforcement baseline.

## Publication rules

1. Public room publication is conservative by default.
2. No public directory publication until moderation, abuse triage, and support runbooks are live.
3. Public rooms are never used as regulated case records.
4. Sensitive conversations pivot into private rooms on the sovereign estate.
5. Public rooms should be treated as readable by anyone who can discover and join them.
6. Encryption is not the default control for public rooms.

## Public-edge moderation minimums

- active moderation bot present in a dedicated moderation room
- documented abuse escalation path
- room publication review process
- operator runbook for spam waves and account abuse
- ability to unpublish, quarantine, and freeze rooms quickly
- support contact and security contact published via Matrix support metadata

## Room publication classes

### Class P0 — not publishable
- regulated case rooms
- private support escalation rooms
- incident rooms
- operator rooms
- agent workspaces with privileged outputs

### Class P1 — publishable only after review
- intake rooms
- community rooms
- product discussion rooms
- public help rooms

## Moderation runbook requirements

Before public publication, the platform must have:
- ban and unban procedure
- room shutdown procedure
- room alias transfer procedure
- abuse evidence capture procedure
- public support contact path
- security escalation path
