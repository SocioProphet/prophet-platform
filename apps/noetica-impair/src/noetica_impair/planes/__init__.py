"""Execution planes. ``get(name)`` returns a plane; all share one interface."""

from __future__ import annotations

from .base import DEFAULT_DOSES, ExecutionPlane, PlaneHandle, RunJob
from .gcp_vm import GCPVMPlane
from .gke import GKEPlane
from .local import LocalPlane

PLANES = {
    "local": LocalPlane,
    "gke": GKEPlane,
    "gcp-vm": GCPVMPlane,
}


def get(name: str, **kw) -> ExecutionPlane:
    if name not in PLANES:
        raise KeyError(f"unknown plane {name!r}; known: {sorted(PLANES)}")
    return PLANES[name](**kw)


__all__ = [
    "DEFAULT_DOSES", "ExecutionPlane", "PlaneHandle", "RunJob",
    "LocalPlane", "GKEPlane", "GCPVMPlane", "PLANES", "get",
]
