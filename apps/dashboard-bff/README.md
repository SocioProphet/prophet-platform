# dashboard-bff

Wave 1 hosted platform service.

## Purpose

`dashboard-bff` is the aggregation layer for operator-facing surfaces. It composes app-facing views from the underlying platform services without pushing thick logic into the frontend.

## Expected dependencies

- identity policy service
- search evidence service
- case triage service
- deep-dive orchestrator
- topology environment service (wave 2)
- artifact release service (wave 2)

## Initial responsibility

- aggregate dashboard views
- normalize action payloads
- expose app-facing projection models
- preserve trace and evidence references
