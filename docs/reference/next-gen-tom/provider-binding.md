# ProviderBinding Platform Contract

## Purpose

`ProviderBinding` is the bridge between a service class and a concrete provider implementation.

A service offering says what can be consumed. A blueprint says how it may be fulfilled. A provider profile says which provider is eligible. A provider binding says which provider implementation is approved for a given service class under a declared policy, evidence, cost, and portability posture.

## Required semantics

A ProviderBinding must declare:

- service class
- provider class
- provider identifier
- blueprint reference
- policy pack references
- portability tier
- native feature exposure
- evidence profile
- cost meter profile
- continuity profile
- exit plan reference
- approval state

## Broker rule

No production service instance should be fulfilled without an approved provider binding unless an explicit exception record exists.
