"""Best-effort integration: the REAL clickhouse-server (the exact digest deploy/values
pins) proving the ReplacingMergeTree idempotency contract end-to-end — a replayed batch
leaves ZERO duplicate rows at FINAL. Unit fakes are the merge gate; this runs when
podman is available and the image can be pulled, and skips loudly otherwise.
"""
from __future__ import annotations

import re
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prophet_materializer_clickhouse.clients import ClickHouseClient  # noqa: E402
from prophet_materializer_clickhouse.materializer import (  # noqa: E402
    MATERIALIZER_NAME, Materializer,
)
from test_materializer import FakeGateway, FakeHellGraph, THREE_EVENTS  # noqa: E402

VALUES = Path(__file__).resolve().parents[3] / "deploy" / "values" / "clickhouse.yaml"


def _image_ref() -> str | None:
    """The digest-pinned image FROM the deployed values file — the test can't drift
    from what prod runs."""
    if not VALUES.exists():
        return None
    m = re.search(r'repository:\s*(\S+)\s*\n.*?tag:\s*"([^"]+)"', VALUES.read_text(), re.S)
    return f"docker.io/{m.group(1)}:{m.group(2)}" if m else None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


pytestmark = pytest.mark.skipif(shutil.which("podman") is None, reason="podman not available")


@pytest.fixture(scope="module")
def clickhouse_url():
    image = _image_ref()
    if image is None:
        pytest.skip("deploy/values/clickhouse.yaml not found (image context?)")
    port = _free_port()
    name = f"materializer-it-{uuid.uuid4().hex[:8]}"
    run = subprocess.run(
        ["podman", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{port}:8123",
         "-e", "CLICKHOUSE_PASSWORD=it-test", image],
        capture_output=True, text=True, timeout=600)
    if run.returncode != 0:
        pytest.skip(f"could not start clickhouse container (best-effort): {run.stderr[-300:]}")
    try:
        import httpx
        deadline = time.time() + 120
        while time.time() < deadline:
            try:
                if httpx.get(f"http://127.0.0.1:{port}/ping", timeout=2).status_code == 200:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        else:
            pytest.skip("clickhouse container never became healthy (best-effort)")
        yield f"http://127.0.0.1:{port}"
    finally:
        subprocess.run(["podman", "rm", "-f", name], capture_output=True, timeout=60)


def test_replayed_batch_deduplicates_in_real_replacingmergetree(clickhouse_url):
    ch = ClickHouseClient(clickhouse_url, user="default", password="it-test")
    m = Materializer(hellgraph=FakeHellGraph(THREE_EVENTS), clickhouse=ch,
                     gateway=FakeGateway(), batch_limit=500)

    m.run_once()                                                   # batch lands + checkpoints
    assert ch.read_checkpoint(MATERIALIZER_NAME) == 12

    # simulate a restart from an OLDER checkpoint: rewind for real, replay the same cut
    ch.execute("TRUNCATE TABLE hellgraph.materializer_checkpoint")
    ch.write_checkpoint(MATERIALIZER_NAME, 5)
    m.run_once()                                                   # replays seq 9 + 12

    raw = int(ch.execute("SELECT count() FROM hellgraph.events").strip())
    final = int(ch.execute("SELECT count() FROM hellgraph.events FINAL").strip())
    distinct = int(ch.execute("SELECT uniqExact(event_id) FROM hellgraph.events").strip())
    assert raw >= 3                                                # replay really re-inserted
    assert final == 3 == distinct                                  # ZERO duplicates at FINAL
    ids = ch.execute("SELECT event_id FROM hellgraph.events FINAL ORDER BY event_id").split()
    assert ids == sorted(["node:n:a", "node:n:b", "edge:EvaluationLink(...)"])
    assert ch.read_checkpoint(MATERIALIZER_NAME) == 12
