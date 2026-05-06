"""Workspace Operation Plane runtime skeleton.

This package is an initial runtime implementation surface for
SocioProphet/prophet-platform#376. It intentionally stays small and depends on
contract-shaped dictionaries so it can consume fixtures from
SocioProphet/prophet-core-contracts without owning canonical schemas.
"""

from .adapters import (
    OperationAdapterError,
    OperationAdapterRegistry,
    StaticAdapterDeclaration,
)
from .boundaries import BoundaryResult
from .commands import (
    COMMAND_TYPES,
    activate_artifact_command,
    admit_artifact_command,
    cancel_operation_command,
    create_operation_command,
    make_command,
    retry_task_command,
)
from .fixtures import (
    CollectingLedgerSink,
    FixtureAgentAuthorityHook,
    FixturePolicyClient,
)
from .runtime import (
    BoundaryDeniedError,
    InMemoryOperationRuntime,
    OperationRuntimeError,
    StateTransitionError,
)

__all__ = [
    "BoundaryDeniedError",
    "BoundaryResult",
    "COMMAND_TYPES",
    "CollectingLedgerSink",
    "FixtureAgentAuthorityHook",
    "FixturePolicyClient",
    "InMemoryOperationRuntime",
    "OperationAdapterError",
    "OperationAdapterRegistry",
    "OperationRuntimeError",
    "StateTransitionError",
    "StaticAdapterDeclaration",
    "activate_artifact_command",
    "admit_artifact_command",
    "cancel_operation_command",
    "create_operation_command",
    "make_command",
    "retry_task_command",
]
