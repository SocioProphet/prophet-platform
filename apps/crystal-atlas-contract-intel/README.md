# Crystal Atlas contract-intel app

This app is the first deployable downstream consumer for the Crystal Atlas lane.

## Responsibilities

- expose liveness
- expose recent downstream intelligence bundles
- expose bundle detail by correlation id
- keep layout compatibility with the platform state conventions already used elsewhere in `prophet-platform`

## Current endpoints

- `/healthz`
- `/v1/contract-intel/event-types`
- `/v1/contract-intel/recent`
- `/v1/contract-intel/{correlation_id}`

## Current service name

`crystal-atlas-contract-intel`
