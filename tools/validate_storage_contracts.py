#!/usr/bin/env python3
"""Validate presence of storage contract files.

This is a minimal conformance check aligned with repo validation style.
"""
import os
import sys

REQUIRED = [
    "contracts/storage/README.md",
    "apps/storage-promotion/README.md",
]

missing = [p for p in REQUIRED if not os.path.exists(p)]

if missing:
    print("Missing storage artifacts:")
    for m in missing:
        print(f" - {m}")
    sys.exit(1)

print("Storage contract validation OK")
