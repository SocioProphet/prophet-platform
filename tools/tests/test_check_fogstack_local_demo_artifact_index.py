from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_demo(output_dir: Path) -> None:
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


def test_check_fogstack_local_demo_artifact_index_passes(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo"
    run_demo(output_dir)

    subprocess.run(
        [
            sys.executable,
            "tools/check_fogstack_local_demo_artifact_index.py",
            "--index",
            str(output_dir / "demo-artifacts.index.json"),
        ],
        check=True,
    )


def test_check_fogstack_local_demo_artifact_index_rejects_tampering(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo"
    run_demo(output_dir)

    html_summary = output_dir / "index.html"
    html_summary.write_text(
        html_summary.read_text(encoding="utf-8") + "\n<!-- tampered -->\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "tools/check_fogstack_local_demo_artifact_index.py",
            "--index",
            str(output_dir / "demo-artifacts.index.json"),
        ],
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0
    assert "artifact digest mismatch" in proc.stderr
    assert "index.html" in proc.stderr
