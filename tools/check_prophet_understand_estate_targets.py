#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPOS = {
    "smart-tree": ["make", "prophet-understand-smoke"],
    "lampstand": ["make", "prophet-understand-smoke"],
    "sherlock-search": ["make", "prophet-understand-smoke"],
    "policy-fabric": ["make", "prophet-understand-smoke"],
    "delivery-excellence": ["make", "prophet-understand-smoke"],
}


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def run(repo: str, path: Path, out_dir: Path) -> dict[str, Any]:
    log_dir = out_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    command = REPOS[repo]
    result = subprocess.run(command, cwd=path, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    log = log_dir / f"{repo}.log"
    log.write_text(result.stdout, encoding="utf-8")
    return {"repo": repo, "path": str(path), "command": command, "returncode": result.returncode, "log": str(log)}


def main() -> None:
    dev_root = Path.home() / "dev"
    out_dir = ROOT / "build/prophet-understand/estate-smokes"
    results = []
    for repo in REPOS:
        repo_path = dev_root / repo
        if not repo_path.exists():
            results.append({"repo": repo, "path": str(repo_path), "returncode": 127, "log": None, "error": "missing repo directory"})
            continue
        results.append(run(repo, repo_path, out_dir))
    summary = {
        "status": "passed" if all(item.get("returncode") == 0 for item in results) else "failed",
        "results": results,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] != "passed":
        fail("one or more Prophet Understand estate smoke targets failed")
    print("OK: Prophet Understand estate smoke targets passed")


if __name__ == "__main__":
    main()
