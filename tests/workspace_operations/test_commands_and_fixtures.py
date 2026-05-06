from __future__ import annotations

import unittest

from prophet_platform.workspace_operations import (
    BoundaryDeniedError,
    BoundaryResult,
    CollectingLedgerSink,
    FixtureAgentAuthorityHook,
    FixturePolicyClient,
    InMemoryOperationRuntime,
    admit_artifact_command,
    cancel_operation_command,
    create_operation_command,
    make_command,
    retry_task_command,
)


class WorkspaceOperationCommandAndFixtureTests(unittest.TestCase):
    def actor(self) -> dict:
        return {"actor_type": "user", "actor_id": "user_test"}

    def operation(self) -> dict:
        return {
            "schema_version": "0.1.0",
            "operation_id": "op_fixture_001",
            "operation_type": "upload.import",
            "actor": self.actor(),
            "target": {"ref_type": "workspace_folder", "ref_id": "docs"},
            "status": "queued",
            "created_at": "2026-05-05T00:00:00Z",
            "updated_at": "2026-05-05T00:00:00Z",
            "idempotency_key": "idem_op_fixture_001",
            "task_ids": [],
            "artifact_ids": [],
            "policy_gate_ids": [],
            "decision_ids": [],
        }

    def test_command_helpers_create_contract_shaped_payloads(self) -> None:
        command = create_operation_command(self.operation(), actor=self.actor())
        self.assertEqual(command["schema_version"], "0.1.0")
        self.assertEqual(command["command_type"], "CreateOperation")
        self.assertEqual(command["operation_id"], "op_fixture_001")
        self.assertEqual(command["idempotency_key"], "idem_op_fixture_001")
        self.assertIn("operation", command["payload"])

        retry = retry_task_command("op_fixture_001", "task_001", actor=self.actor())
        self.assertEqual(retry["command_type"], "RetryTask")
        self.assertEqual(retry["task_id"], "task_001")

        cancel = cancel_operation_command("op_fixture_001", actor=self.actor(), reason="test")
        self.assertEqual(cancel["command_type"], "CancelOperation")
        self.assertEqual(cancel["payload"]["reason"], "test")

        admit = admit_artifact_command("op_fixture_001", "artifact_001", actor=self.actor())
        self.assertEqual(admit["command_type"], "AdmitArtifact")
        self.assertEqual(admit["payload"]["artifact_id"], "artifact_001")

    def test_unknown_command_type_fails_fast(self) -> None:
        with self.assertRaises(ValueError):
            make_command("UnknownCommand", operation_id="op", actor=self.actor())

    def test_fixture_policy_client_can_deny_specific_command(self) -> None:
        policy = FixturePolicyClient(
            decisions={
                "CreateOperation": BoundaryResult(
                    allowed=False,
                    reason="fixture block",
                    responsible_actor="tenant_admin",
                    remediation_options=("request_override",),
                )
            }
        )
        runtime = InMemoryOperationRuntime(policy_client=policy)

        with self.assertRaises(BoundaryDeniedError):
            runtime.create_operation(self.operation())

    def test_collecting_ledger_sink_derives_evidence_records(self) -> None:
        ledger = CollectingLedgerSink()
        runtime = InMemoryOperationRuntime(ledger_sink=ledger)
        runtime.create_operation(self.operation())

        self.assertEqual(len(ledger.events), 1)
        self.assertEqual(len(ledger.evidence_records), 1)
        evidence = ledger.evidence_records[0]
        self.assertEqual(evidence["evidence_type"], "OperationEventLedgerEntry")
        self.assertEqual(evidence["operation_id"], "op_fixture_001")

    def test_fixture_agent_authority_can_deny_actor_action(self) -> None:
        authority = FixtureAgentAuthorityHook()
        authority.deny("user_test", "CreateOperation", reason="actor scope denied")
        runtime = InMemoryOperationRuntime(agent_authority=authority)

        with self.assertRaises(BoundaryDeniedError) as raised:
            runtime.create_operation(self.operation())

        self.assertIn("actor scope denied", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
