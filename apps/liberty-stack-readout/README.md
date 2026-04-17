# Liberty Stack readout app

This app is the first thin operator-facing surface for the Liberty Stack runtime lane.

## Purpose

Expose a minimal HTTP readout for:
- Liberty Stack receipts
- verification records
- workflow event refs
- a summarized subject status view

## First endpoints

- `/healthz`
- `/v1/liberty-stack/readout`

## Current status

This is intentionally minimal and file-backed. It is a thin surface over the receipt and readout helpers already landed in the repo.
