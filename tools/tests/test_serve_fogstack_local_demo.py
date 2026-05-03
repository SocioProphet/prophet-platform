from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def test_serve_fogstack_local_demo_index(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo"
    subprocess.run(
        [
            sys.executable,
            "tools/run_fogstack_local_demo.py",
            "--pack",
            "access",
            "--output-dir",
            str(output_dir),
        ],
        check=True,
    )

    proc = subprocess.Popen(
        [
            sys.executable,
            "tools/serve_fogstack_local_demo.py",
            "--directory",
            str(output_dir),
            "--host",
            "127.0.0.1",
            "--port",
            "0",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None
        line = proc.stdout.readline().strip()
        assert line.startswith("Serving FogStack local demo at http://127.0.0.1:")
        url = line.removeprefix("Serving FogStack local demo at ")

        body = ""
        last_error: Exception | None = None
        for _ in range(20):
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    body = response.read().decode("utf-8")
                break
            except Exception as exc:  # pragma: no cover - retry guard for slow CI sockets
                last_error = exc
                time.sleep(0.1)
        else:
            raise AssertionError(f"server did not respond: {last_error}")

        assert "<title>FogStack Local Demo Summary</title>" in body
        assert "FogStack Local Demo Summary" in body
        assert "fogstack.access" in body
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
