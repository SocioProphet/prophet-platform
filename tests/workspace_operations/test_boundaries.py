from __future__ import annotations

import unittest

from prophet_platform.workspace_operations import (
    BoundaryDeniedError,
    BoundaryResult,
    InMemoryOperationRuntime,
)


class DenyingPolicyClient:
    def evaluate_command(self, command, operation=None):
        return BoundaryResult(
            allowed=False,
            reason="demo policy denial",
            responsible_actor="tenant_admin",
            remediation_options=("request_override",),
        )


class CollectingLedgerSink:
    def __init__(self) -> None:
        self.events = []

    def record_event(self, event) -> None:
        self.events.append(dict(event))


class WorkspaceOperationBoundaryTests(unittest.TestCase):
    def operation(self) -> dict:
        return {
            "schema_version": "0.1.0",
            "operation_id": "op_boundary_001",
            "operation_type": "upload.import",
            "actor": {"actor_type": "user", "actor_id": "user_test"},
            "target": {"ref_type": "workspace_folder", "ref_id": "docs"},
            "status": "queued",
            "created_at": "2026-05-05T00:00:00Z",
            "updated_at": "2026-05-05T00:00:00Z",
            "idempotency_key": "idem_op_boundary_001",
            "task_ids": [],
            "artifact_ids": [],
            "policy_gate_ids": [],
            "decision_ids": [],
        }

    def test_policy_boundary_denial_blocks_create(self) -> None:
        runtime = InMemoryOperationRuntime(policy_client=DenyingPolicyClient())

        with self.assertRaises(BoundaryDeniedError) as raised:
            runtime.create_operation(self.operation())

        message = str(raised.exception)
        self.assertIn("policy boundary denied command", message)
        self.assertIn("tenant_admin", message)

    def test_ledger_sink_receives_runtime_events(self) -> None:
        ledger = CollectingLedgerSink()
        runtime = InMemoryOperationRuntime(ledger_sink=ledger)
        runtime.create_operation(self.operation())

        self.assertEqual(len(ledger.events), 1)
        self.assertEqual(ledger.events[0]["event_type"], "workspace.operation.created")
        self.assertEqual(ledger.events[0]["operation_id"], "op_boundary_001")


if __name__ == "__main__":
    unittest.main()
