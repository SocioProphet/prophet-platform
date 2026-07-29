from __future__ import annotations

import copy
import json
from importlib import resources
from typing import Any

import pytest

from device_service import contract


def _profile(name: str) -> dict[str, Any]:
    raw = (resources.files("device_service") / "profiles" / f"{name}.json").read_text("utf-8")
    return json.loads(raw)


@pytest.fixture
def virtual_profile() -> dict[str, Any]:
    return contract.load_profile(_profile("virtual-room-sensor"))


@pytest.fixture
def ble_profile() -> dict[str, Any]:
    return contract.load_profile(_profile("acme-th100-ble"))


@pytest.fixture
def reading(virtual_profile) -> dict[str, Any]:
    return contract.build_reading(
        profile=virtual_profile,
        device_ref="urn:srcos:device:room_sensor_01",
        metric="temperature",
        value=21.5,
        quality="ok",
        observed_at="2026-07-29T09:15:00.000Z",
        received_at="2026-07-29T09:15:00.042Z",
        wall_time="2026-07-29T09:15:00.042Z",
        logical_time=117,
        sequence_ref=117,
        workspace_ref="urn:srcos:workspace:citizen_home_demo",
        branch_ref="urn:srcos:branch:home_main",
        actor_ref="urn:srcos:agent:device_service",
        raw_payload={"driver": "virtual", "tick": 117},
    )


class FakeWriter:
    """Records graph writes; can be told to fail after N successful ops."""

    def __init__(self, fail_after: int | None = None) -> None:
        self.nodes: list[tuple] = []
        self.edges: list[tuple] = []
        self.fail_after = fail_after
        self.ops = 0

    def _maybe_fail(self) -> None:
        from device_service.clients import EmitError

        if self.fail_after is not None and self.ops >= self.fail_after:
            raise EmitError("fake hellgraph outage")
        self.ops += 1

    def post_node(self, node_id, labels, properties) -> None:
        self._maybe_fail()
        self.nodes.append((node_id, list(labels), properties))

    def post_edge(self, label, from_id, to_id) -> None:
        self._maybe_fail()
        self.edges.append((label, from_id, to_id))


class FakeGateway:
    """Records seals; can refuse. Memoizes by spec, like the real gateway."""

    def __init__(self, refuse: bool = False) -> None:
        self.calls: list[dict] = []
        self.refuse = refuse
        self._memo: dict[str, dict] = {}

    def mint(self, *, device_ref, from_cursor, to_cursor, row_count, batch_hash) -> dict:
        from device_service.clients import GatewayError

        if self.refuse:
            raise GatewayError("fake gateway refusal")
        spec = {
            "device_ref": device_ref, "from_cursor": from_cursor, "to_cursor": to_cursor,
            "row_count": row_count, "batch_hash": batch_hash,
        }
        self.calls.append(spec)
        key = json.dumps(spec, sort_keys=True)
        if key in self._memo:
            return self._memo[key]
        receipt = {"id": f"sha256:receipt{len(self._memo):04d}", "kind": "materialize"}
        self._memo[key] = receipt
        return receipt


@pytest.fixture
def fake_writer() -> FakeWriter:
    return FakeWriter()


@pytest.fixture
def fake_gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def mutate():
    def _mutate(doc: dict, **changes: Any) -> dict:
        out = copy.deepcopy(doc)
        out.update(changes)
        return out

    return _mutate
