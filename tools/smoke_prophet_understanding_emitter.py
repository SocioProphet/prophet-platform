#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EMITTER = ROOT / "tools/emit_prophet_understanding.py"


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON emitted: {exc}")
    if not isinstance(value, dict):
        fail("emitted artifact must be a JSON object")
    return value


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="prophet-understand-") as raw_tmp:
        tmp = Path(raw_tmp)
        repo = tmp / "fixture-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Fixture Repo\n\nSmoke fixture.\n", encoding="utf-8")
        (repo / "schemas").mkdir()
        (repo / "schemas/example.schema.json").write_text('{"type":"object"}\n', encoding="utf-8")
        (repo / "src").mkdir()
        (repo / "src/main.py").write_text("def main():\n    return 0\n", encoding="utf-8")
        (repo / "target").mkdir()
        (repo / "target/generated.txt").write_text("generated\n", encoding="utf-8")

        out = repo / ".prophet/prophet-understanding.json"
        result = subprocess.run(
            [sys.executable, str(EMITTER), "--repo", str(repo), "--out", str(out), "--repo-full-name", "SocioProphet/prophet-understand-fixture"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode != 0:
            print(result.stdout, file=sys.stderr)
            fail("emitter exited nonzero")
        if not out.exists():
            fail("emitter did not create artifact")
        artifact = load(out)
        if artifact.get("schema_version") != "prophet-understanding.v0":
            fail("schema_version missing or invalid")
        repo_meta = artifact.get("repo", {})
        if repo_meta.get("full_name") != "SocioProphet/prophet-understand-fixture":
            fail("repo.full_name mismatch")
        if not str(repo_meta.get("artifact_hash", "")).startswith("sha256:") or repo_meta.get("artifact_hash") == "sha256:pending":
            fail("artifact hash was not finalized")
        nodes = artifact.get("nodes", [])
        if not isinstance(nodes, list) or len(nodes) < 4:
            fail("too few nodes emitted")
        kinds = {node.get("kind") for node in nodes if isinstance(node, dict)}
        for kind in {"repo", "document", "schema", "module"}:
            if kind not in kinds:
                fail(f"missing expected node kind: {kind}")
        receipts = {receipt.get("id") for receipt in artifact.get("provenance_receipts", []) if isinstance(receipt, dict)}
        if "receipt:skipped-paths" not in receipts:
            fail("expected skipped paths receipt for target directory")
        skipped = repo_meta.get("metadata", {}).get("skipped_paths", [])
        if not skipped:
            fail("expected skipped path metadata")
        edges = artifact.get("edges", [])
        node_ids = {node.get("id") for node in nodes if isinstance(node, dict)}
        for edge in edges:
            if not isinstance(edge, dict):
                fail("edge must be object")
            if edge.get("source") not in node_ids or edge.get("target") not in node_ids:
                fail(f"edge references missing endpoint: {edge.get('id')}")
        print("OK: Prophet Understand emitter smoke passed")


if __name__ == "__main__":
    main()
