# Smart Spaces / Built Environment Domain Home Decision

Status: open decision
Date: 2026-04-27
Owner surface: prophet-platform

## Context

The earlier phrase "home IoT" is too narrow.

The actual domain is **Smart Spaces / Built Environment Fabric**. It includes:

- smart homes;
- classrooms;
- hotel rooms;
- boardrooms;
- offices;
- campuses;
- facilities;
- smart-building systems;
- smart-city-facing space interfaces.

These environments share a common pattern: local devices, occupancy, automation, privacy, physical assets, access control, environmental sensing, energy, safety, and human approval.

## Decision to make

We have not yet decided whether Smart Spaces should live in:

1. `gaia-world-model`, as part of the broader world/asset/facility twin;
2. `orion-field-intelligence`, as event and sensor semantics only;
3. `sociosphere`, as site/workspace/fleet governance;
4. `prophet-platform`, as shared platform contracts;
5. a future dedicated repo, such as `smart-spaces-fabric` or `built-environment-fabric`.

## Current decision

Do **not** create a dedicated repo yet.

Do **not** place speculative Smart Spaces runtime assets into Lattice Forge.

Do **not** place unresolved Smart Spaces domain schemas into GAIA, OFIF, or SocioSphere by assumption.

Use `prophet-platform` as the temporary decision home for domain-boundary notes until the authority split is clear.

## Working authority split

Potential authority boundaries:

| Concern | Likely authority |
| --- | --- |
| Physical space / building / room world-state | GAIA or future domain repo |
| Device or sensor observations | OFIF |
| Local automation runtime | Agentplane + future domain/runtime boundary |
| Runtime packaging | Lattice Forge only after executable boundary is defined |
| Local state sampling | Lampstand |
| Search / discovery | Sherlock |
| Site, org, fleet, role, policy composition | SocioSphere |
| Host lifecycle and edge node management | SourceOS / nlboot |
| Cross-domain platform contracts | prophet-platform |

## Candidate objects

These are candidate contracts, not yet assigned to a final repo:

- `SpaceTwinRecord`
- `RoomTwinRecord`
- `BuildingTwinRecord`
- `DeviceTwinRecord`
- `FabricRecord`
- `AutomationPolicyRecord`
- `OccupancyObservation`
- `AccessControlEvent`
- `EnergyObservation`
- `EnvironmentalComfortObservation`
- `BystanderPrivacyPolicy`
- `OccupancyPrivacyPolicy`
- `AutomationDecisionCard`

## Standards and systems to evaluate

- Matter;
- Thread;
- Home Assistant;
- MQTT / Sparkplug B;
- OPC UA where industrial building systems are involved;
- BACnet / building automation concepts;
- Brick Schema;
- Project Haystack;
- RealEstateCore;
- W3C Web of Things Thing Description;
- OGC SensorThings;
- IFC / buildingSMART for BIM integration;
- CityGML for city-scale built environment context.

## Privacy and safety rule

Smart spaces involve occupancy, cameras, audio, access control, presence, comfort, and potentially bystander data.

No serious implementation should proceed without:

- privacy impact assessment;
- surveillance risk classification;
- bystander privacy policy;
- automation approval policy;
- audit and override records;
- clear human-in-the-loop boundaries for sensitive actions.

## Open questions

1. Is Smart Spaces primarily a GAIA domain twin or a separate domain repo?
2. Should device-level semantics live in OFIF only, with space semantics elsewhere?
3. Should SocioSphere own the site/building/floor/room governance model?
4. Should a future repo focus on adapters to Home Assistant / Matter / Thread / BACnet?
5. How much should be common with industrial IoT and control tower objects?

## Interim rule

Until this decision is closed, only create:

- planning docs in `prophet-platform`;
- explicitly cross-domain references in the master plan;
- issues requesting analysis.

Do not create speculative implementation fixtures in Lattice Forge or any future runtime repo.
