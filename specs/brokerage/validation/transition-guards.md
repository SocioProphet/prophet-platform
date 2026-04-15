# Transition Guards

## Request lifecycle

Allowed transitions:
- Draft -> Submitted
- Submitted -> Classified
- Classified -> PendingPolicy
- PendingPolicy -> PendingApproval or Approved or Denied
- PendingApproval -> Approved or Denied
- Approved -> InFulfillment
- InFulfillment -> Registered
- Registered -> InService
- InService -> Modified or Retired

## Hard guards

- A request cannot enter `InFulfillment` without a blueprint and policy decision.
- A request cannot enter `InService` without instance registration, owner assignment, and observability hooks.
- A service cannot be marked retired until evidence and cost records are closed.

## Benefit-credit guards

A capability does not receive benefit credit unless:
1. the request path is governed through catalog or API,
2. the automated path has displaced the manual path,
3. instances auto-register,
4. evidence is captured automatically,
5. old manual routing is retired or usage-capped.
