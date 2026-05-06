from __future__ import annotations

import unittest

from prophet_platform.workspace_operations import (
    OperationAdapterError,
    OperationAdapterRegistry,
    StaticAdapterDeclaration,
)


class WorkspaceOperationAdapterRegistryTests(unittest.TestCase):
    def test_register_and_fetch_static_adapter_declaration(self) -> None:
        registry = OperationAdapterRegistry()
        adapter = StaticAdapterDeclaration(
            operation_type="upload.import",
            supported_artifact_types=("markdown", "pdf"),
            required_capabilities=("filesystem.read",),
            policy_gates_invoked=("metadata.required",),
            diagnostic_redaction_rules=("cookies", "bearer_tokens"),
            extra={"test_fixtures": ["upload-import-happy-path.json"]},
        )

        registry.register(adapter)

        self.assertTrue(registry.has("upload.import"))
        self.assertEqual(registry.get("upload.import"), adapter)
        self.assertEqual(registry.operation_types(), ["upload.import"])

        declaration = registry.declarations()[0]
        self.assertEqual(declaration["schema_version"], "0.1.0")
        self.assertEqual(declaration["operation_type"], "upload.import")
        self.assertEqual(declaration["supported_artifact_types"], ["markdown", "pdf"])
        self.assertEqual(declaration["test_fixtures"], ["upload-import-happy-path.json"])

    def test_duplicate_registration_fails_closed(self) -> None:
        registry = OperationAdapterRegistry()
        adapter = StaticAdapterDeclaration(operation_type="terminal.command.run", supported_artifact_types=("command_result",))

        registry.register(adapter)
        with self.assertRaises(OperationAdapterError):
            registry.register(adapter)

    def test_unknown_adapter_lookup_fails_closed(self) -> None:
        registry = OperationAdapterRegistry()

        with self.assertRaises(OperationAdapterError):
            registry.get("memory.ingest.start")


if __name__ == "__main__":
    unittest.main()
