"""Workspace Operation Plane runtime skeleton.

This package is an initial runtime implementation surface for
SocioProphet/prophet-platform#376. It intentionally stays small and depends on
contract-shaped dictionaries so it can consume fixtures from
SocioProphet/prophet-core-contracts without owning canonical schemas.
"""

from .runtime import (
    InMemoryOperationRuntime,
    OperationRuntimeError,
    StateTransitionError,
)

__all__ = [
    "InMemoryOperationRuntime",
    "OperationRuntimeError",
    "StateTransitionError",
]
