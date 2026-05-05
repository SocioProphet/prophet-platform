from __future__ import annotations

import unittest

from prophet_platform.workspace_operations import (
    InMemoryOperationRuntime,
    StateTransitionError,
)


class WorkspaceOperationRuntimeTests(unittest.TestCase):
    def operation(self, status: str = "queued") -> dict:
        return {
            "schema_version": "0.1.0",
            "operation_id": "op_test_001",
            "operation_type": "upload.import",
            "actor": {"actor_type": "user", "actor_id": "user_test"},
            "target": {"ref_type": "workspace_folder", "ref_id": "docs"},
            "status": status,
            "created_at": "2026-05-05T00:00:00Z",
            "updated_at": "2026-05-05T00:00:00Z",
            "idempotency_key": "idem_op_test_001",
            "task_ids": [],
            "artifact_ids": [],
            "policy_gate_ids": [],
            "decision_ids": [],
        }

    def task(self, status: str = "queued", retryable: bool = True) -> dict:
        return {
            "schema_version": "0.1.0",
            "task_id": "task_test_001",
            "operation_id": "op_test_001",
            "task_type": "file.upload",
            "status": status,
            "stage": "queued",
            "progress": 0,
            "retry_count": 0,
            "retryable": retryable,
            "auto_retry_allowed": False,
            "idempotency_key": "idem_task_test_001",
        }

    def artifact(self, admission_state: str = "stored", activation_state: str = "inactive") -> dict:
        return {
            "schema_version": "0.1.0",
            "artifact_id": "artifact_test_001",
            "artifact_type": "markdown",
            "display_name": "test.md",
            "stable_identity": "workspace://artifact/artifact_test_001",
            "created_by_operation_id": "op_test_001",
            "admission_state": admission_state,
            "activation_state": activation_state,
            "created_at": "2026-05-05T00:00:00Z",
        }

    def test_create_operation_emits_event_and_snapshot(self) -> None:
        runtime = InMemoryOperationRuntime()
        snapshot = runtime.create_operation(self.operation())

        self.assertEqual(snapshot["operation_id"], "op_test_001")
        self.assertEqual(snapshot["status"], "queued")
        self.assertEqual(snapshot["event_count"], 1)
        self.assertEqual(runtime.events[0]["event_type"], "workspace.operation.created")

    def test_transition_operation_respects_state_machine(self) -> None:
        runtime = InMemoryOperationRuntime()
        runtime.create_operation(self.operation())
        snapshot = runtime.transition_operation("op_test_001", "preflighting")

        self.assertEqual(snapshot["status"], "preflighting")

        with self.assertRaises(StateTransitionError):
            runtime.transition_operation("op_test_001", "completed")

    def test_task_retry_requires_retryable_task(self) -> None:
        runtime = InMemoryOperationRuntime()
        runtime.create_operation(self.operation())
        runtime.attach_task("op_test_001", self.task(status="failed", retryable=False))

        with self.assertRaises(StateTransitionError):
            runtime.retry_task("op_test_001", "task_test_001")

    def test_cancel_operation_uses_canceling_then_canceled(self) -> None:
        runtime = InMemoryOperationRuntime()
        runtime.create_operation(self.operation(status="running"))
        snapshot = runtime.cancel_operation("op_test_001")

        self.assertEqual(snapshot["status"], "canceled")
        event_types = [event["event_type"] for event in runtime.events]
        self.assertIn("workspace.operation.status_changed", event_types)

    def test_artifact_admission_activation_rules(self) -> None:
        runtime = InMemoryOperationRuntime()
        runtime.create_operation(self.operation())
        detail = runtime.get_operation_detail("op_test_001")
        detail["artifacts"]["artifact_test_001"] = self.artifact()

        # Reload through fixture bundle so artifact attachment uses the public path for now.
        runtime = InMemoryOperationRuntime()
        runtime.load_fixture_bundle({"operation": self.operation(), "artifact": self.artifact()})
        runtime.admit_artifact("op_test_001", "artifact_test_001")
        snapshot = runtime.activate_artifact("op_test_001", "artifact_test_001")

        self.assertIn("artifact_test_001", snapshot["artifact_ids"])

    def test_load_fixture_bundle_materializes_counts(self) -> None:
        runtime = InMemoryOperationRuntime()
        snapshot = runtime.load_fixture_bundle(
            {
                "operation": {
                    **self.operation(),
                    "task_ids": ["task_test_001"],
                    "artifact_ids": ["artifact_test_001"],
                },
                "task": self.task(),
                "artifact": self.artifact(),
            }
        )

        self.assertEqual(snapshot["task_counts"], {})
        loaded = runtime.get_operation_snapshot("op_test_001")
        self.assertEqual(loaded["task_counts"], {"queued": 1})
        self.assertIn("artifact_test_001", loaded["artifact_ids"])


if __name__ == "__main__":
    unittest.main()
