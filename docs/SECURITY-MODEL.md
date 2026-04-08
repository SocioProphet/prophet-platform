# Security model

## Boundary summary

- Browsers are untrusted.
- The HTTP gateway is the browser-facing ingress boundary.
- Internal service traffic is expected to use the pinned TriTRPC v1 profile.
- Platform contracts and receipts are evidence artifacts, not authority by themselves.
- Standards remain upstream; platform services consume them by pinned revision.

## Current phase limits

This phase establishes a minimal authenticated service-to-service bootstrap path and local receipt artifacts. It does **not** claim a complete production authz, key lifecycle, replay-window, or export-governance implementation yet.

## Immediate expectations

- no local shadow transport spec
- explicit topology choice for UDS vs TCP
- canonical event/evidence receipt artifacts
- local daemons are first-class service types, not deployment mistakes
