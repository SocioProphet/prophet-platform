# cloudshell-fog Access Profile v0

This document explains how the local `cloudshell-fog` platform artifacts align to the Fog Stack Access offering profile.

## Purpose

The connected Fog Stack documents already define the offering-level expectations for `fogstack.access`.

This document provides the local platform-side interpretation so operators and release engineers can see which expectations are already represented in `prophet-platform`.

## Bound capability and substrate

- primary source capability: `SocioProphet/cloudshell-fog`
- primary substrate: `SocioProphet/prophet-platform`

## Local profile contract

Machine-readable local contract:

- `contracts/cloudshell-fog/fogstack-access-profile-v0.json`

This contract captures the minimum offering-level expectations that the local deployment bundle should satisfy.

## What it currently aligns with

- OIDC browser-edge identity model
- short-lived session attach token model
- policy lane and runtime-v2 lane in the platform repo
- required evidence families: bundle manifest, component-version manifest, SBOM, provenance, compatibility statement
- required audit event family for the shell lifecycle

## What remains environment-owned

This local profile does not by itself provide:

- a published production image digest
- a selected secret-source implementation
- a selected signature trust implementation
- a resolved federal fallback region

Those still belong in the production decision record.
