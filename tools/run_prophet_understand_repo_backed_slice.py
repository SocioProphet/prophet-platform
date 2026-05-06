#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPOS = {
    "smart_tree": "smart-tree",
    "prophet_platform": "prophet-platform",
    "lampstand": "lampstand",
    "sherlock_search": "sherlock-search",
    "policy_fabric": "policy-fabric",
    "delivery_excellence": "delivery-excellence",
}


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def run(name: str, command: list[str], cwd: Path, log_dir: Path) -> dict[str, Any]:
    log_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    log_path = log_dir / f"{name}.log"
    log_path.write_text(result.stdout, encoding="utf-8")
    return {
        "name": name,
        "cwd": str(cwd),
        "command": command,
        "returncode": result.returncode,
        "log": str(log_path),
    }


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        fail(f"missing {label}: {path}")


def require_repo(path: Path, label: str) -> None:
    if not path.exists() or not path.is_dir():
        fail(f"missing repo directory for {label}: {path}")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON at {path}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the real repo-backed Prophet Understand vertical slice across sibling repos.")
    parser.add_argument("--dev-root", default=str(Path.home() / "dev"), help="Directory containing the SocioProphet repos")
    parser.add_argument("--target-repo", default="smart-tree", help="Repo directory to scan")
    parser.add_argument("--target-full-name", default="SocioProphet/smart-tree", help="owner/name for the scanned repo")
    parser.add_argument("--query", default="what depends on this contract?", help="Sherlock query to run against the generated index")
    parser.add_argument("--out-dir", default=str(ROOT / "build/prophet-understand/repo-backed"), help="Output directory for generated artifacts")
    args = parser.parse_args()

    dev_root = Path(args.dev_root).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    log_dir = out_dir / "logs"

    paths = {name: dev_root / rel for name, rel in DEFAULT_REPOS.items()}
    target_repo = dev_root / args.target_repo
    paths["target_repo"] = target_repo

    for label, path in paths.items():
        require_repo(path, label)

    smart_emitter = paths["smart_tree"] / "tools/emit_prophet_understanding.py"
    platform_validator = paths["prophet_platform"] / "tools/validate_prophet_understand.py"
    lampstand_indexer = paths["lampstand"] / "tools/index_prophet_understanding.py"
    sherlock_searcher = paths["sherlock_search"] / "tools/search_prophet_understanding.py"
    policy_evaluator = paths["policy_fabric"] / "tools/evaluate_prophet_understand_policy.py"
    delivery_scorer = paths["delivery_excellence"] / "tools/score_prophet_understand.py"

    for label, path in {
        "smart_tree emitter": smart_emitter,
        "platform validator": platform_validator,
        "lampstand indexer": lampstand_indexer,
        "sherlock searcher": sherlock_searcher,
        "policy evaluator": policy_evaluator,
        "delivery scorer": delivery_scorer,
    }.items():
        require_file(path, label)

    artifact = target_repo / ".prophet/prophet-understanding.json"
    index_out = out_dir / "lampstand-index.json"
    search_out = out_dir / "sherlock-search.json"
    policy_out = out_dir / "policy-decision.json"
    score_out = out_dir / "delivery-scorecard.json"
    summary_out = out_dir / "repo-backed-summary.json"

    steps = [
        run(
            "01-smart-tree-emit",
            [sys.executable, str(smart_emitter), "--repo", str(target_repo), "--out", str(artifact), "--repo-full-name", args.target_full_name],
            paths["smart_tree"],
            log_dir,
        ),
        run(
            "02-platform-validate",
            [sys.executable, str(platform_validator), "--artifact", str(artifact), "--skip-doc"],
            paths["prophet_platform"],
            log_dir,
        ),
        run(
            "03-lampstand-index",
            [sys.executable, str(lampstand_indexer), "--artifact", str(artifact), "--out", str(index_out)],
            paths["lampstand"],
            log_dir,
        ),
        run(
            "04-sherlock-search",
            [sys.executable, str(sherlock_searcher), "--index", str(index_out), "--query", args.query, "--out", str(search_out)],
            paths["sherlock_search"],
            log_dir,
        ),
        run(
            "05-policy-evaluate",
            [sys.executable, str(policy_evaluator), "--artifact", str(artifact), "--out", str(policy_out)],
            paths["policy_fabric"],
            log_dir,
        ),
        run(
            "06-delivery-score",
            [sys.executable, str(delivery_scorer), "--artifact", str(artifact), "--out", str(score_out)],
            paths["delivery_excellence"],
            log_dir,
        ),
    ]

    failed = [step for step in steps if step["returncode"] != 0]
    summary: dict[str, Any] = {
        "target_repo": str(target_repo),
        "target_full_name": args.target_full_name,
        "artifact": str(artifact),
        "index": str(index_out),
        "search": str(search_out),
        "policy": str(policy_out),
        "scorecard": str(score_out),
        "steps": steps,
        "status": "failed" if failed else "passed",
    }

    if artifact.exists():
        artifact_json = load_json(artifact)
        summary["artifact_node_count"] = len(artifact_json.get("nodes", [])) if isinstance(artifact_json, dict) else None
        summary["artifact_edge_count"] = len(artifact_json.get("edges", [])) if isinstance(artifact_json, dict) else None
    if index_out.exists():
        index_json = load_json(index_out)
        summary["index_record_count"] = len(index_json) if isinstance(index_json, list) else None
    if search_out.exists():
        search_json = load_json(search_out)
        summary["search_result_count"] = search_json.get("result_count") if isinstance(search_json, dict) else None
    if policy_out.exists():
        policy_json = load_json(policy_out)
        summary["policy_state"] = policy_json.get("policy_state") if isinstance(policy_json, dict) else None
    if score_out.exists():
        score_json = load_json(score_out)
        summary["scorecard_state"] = score_json.get("scorecard_state") if isinstance(score_json, dict) else None

    out_dir.mkdir(parents=True, exist_ok=True)
    summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))
    if failed:
        fail(f"repo-backed Prophet Understand slice failed; inspect logs under {log_dir}")
    print("OK: repo-backed Prophet Understand vertical slice passed")


if __name__ == "__main__":
    main()
