# Liberty Stack evidence readout

## Purpose

This note defines the first thin operator-visible readout surface for the Liberty Stack lane in `prophet-platform`.

It is intentionally simple: the goal is to make receipts, verification records, and workflow events inspectable before a larger operator UI exists.

## Minimum visible artifacts

A first readout surface SHOULD show:
- action receipts
- verification record refs
- evidence bundle refs
- replay request and replay completion events
- cutover approval events
- current status for a selected subject

## First readout questions

For any selected subject, the surface SHOULD make it easy to answer:
1. what action was attempted
2. whether it succeeded, failed, or was blocked
3. which evidence bundle supports the current state
4. whether replay was requested and how it completed
5. whether cutover approval exists

## Deliberate limits

This first readout note does not require a full UI implementation. A CLI, JSON view, or thin HTTP surface is acceptable in the first runtime slice as long as the evidence and workflow state are operator-visible.
