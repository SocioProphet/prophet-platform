"""Workspace Operation Plane runtime skeleton.

This package is an initial runtime implementation surface for
SocioProphet/prophet-platform#376. It intentionally stays small and depends on
contract-shaped dictionaries so it can consume fixtures from
SocioProphet/prophet-core-contracts without owning canonical schemas.
"""

from .boundaries import BoundaryResult
from .runtime import (
    BoundaryDeniedError,
    InMemoryOperationRuntime,
    OperationRuntimeError,
    StateTransitionError,
)

__all__ = [
    "BoundaryDeniedError",
    "BoundaryResult",
    "InMemoryOperationRuntime",
    "OperationRuntimeError",
    "StateTransitionError",
]
